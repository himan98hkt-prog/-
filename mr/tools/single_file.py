# -*- coding: utf-8 -*-
"""꾸러미를 **파일 하나**로 묶는다 — 두 번 누르면 열리는 「들어보기」.

왜 필요한가. 정적 꾸러미는 파일이 33개라 **웹서버가 있어야** 돕니다.
`file://` 로 `index.html` 을 열면 브라우저가 같은 폴더의 파일조차 `fetch`
하지 못하게 막습니다(출처가 `null` 이라 전부 CORS 거부). 그래서 원장님이
압축을 풀고 `index.html` 을 두 번 눌러도 **빈 화면**이 나옵니다.

파이썬을 깔기 전에 소리부터 들어 보고 싶은 분에게 그 빈 화면은 곧 "안 되는
프로그램"입니다. 그래서 곡 목록과 반주 MIDI 를 **문서 안에 넣고**, 앱이
부르는 `fetch` 만 가로채 그 안에서 꺼내 줍니다. 앱 코드는 한 줄도 안 고칩니다.

    python3 tools/single_file.py /tmp/pkg -o 들어보기.html

한계는 분명히 해 둡니다 — 이건 **들어 보는 용도**입니다. 악보를 넣어 반주를
만드는 것은 제작 서버(`serve.py`)가 하고, 그건 파이썬이 필요합니다.
"""
import argparse
import base64
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MR = os.path.dirname(HERE)

# 의존성 순서. 뒤엣것이 앞엣것을 부르므로 이 순서로 blob 을 만들어야 한다.
MODULES = ('midi.js', 'synth.js', 'store.js', 'engine.js', 'app.js')
STYLES = ('tokens.css', 'player.css')


class BuildError(Exception):
    pass


def read_text(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def collect(pkg):
    """꾸러미에서 넣을 것을 모은다."""
    bundle_path = os.path.join(pkg, 'api', 'player', 'bundle')
    if not os.path.exists(bundle_path):
        raise BuildError(
            f'정적 꾸러미가 아닙니다: {pkg}\n'
            '  python3 catalog_cli.py package <폴더> 로 먼저 만드세요.')
    bundle = json.loads(read_text(bundle_path))

    midi_dir = os.path.join(pkg, 'api', 'player', 'midi')
    midi = {}
    for name in sorted(os.listdir(midi_dir)):
        path = os.path.join(midi_dir, name)
        if os.path.isfile(path):
            midi[name] = base64.b64encode(read_bytes(path)).decode('ascii')

    # 번들이 가리키는 반주가 **전부** 들어갔는지 본다. 하나라도 빠지면 그 곡만
    # 조용히 안 나므로, 만들 때 잡는 편이 낫다.
    missing = []
    for song in bundle.get('songs', []):
        for v in song.get('variants', []):
            want = v['url'].split('?')[0].rsplit('/', 1)[-1]
            if want not in midi:
                missing.append(want)
    if missing:
        raise BuildError(f'반주 파일이 꾸러미에 없습니다: {missing[:3]}')

    src = {n: read_text(os.path.join(pkg, 'js', n)) for n in MODULES}
    css = '\n'.join(read_text(os.path.join(pkg, n)) for n in STYLES)
    return bundle, midi, src, css


def body_of(index_html):
    """꾸러미 index.html 에서 `<body>` 안쪽만. 화면 구조를 베끼지 않기 위해서다.

    여기서 손으로 다시 적으면 플레이어가 바뀔 때 이 파일만 낡는다.
    """
    m = re.search(r'<body[^>]*>(.*?)</body>', index_html, re.S)
    if not m:
        raise BuildError('index.html 에서 <body> 를 못 찾았습니다')
    body = m.group(1)
    # 스크립트 태그는 우리가 따로 넣는다 (blob 로더)
    return re.sub(r'<script\b.*?</script>', '', body, flags=re.S).strip()


LOADER = r"""
(function () {
  'use strict';

  // --- 앱이 부르는 주소를 가로챈다 -------------------------------------------
  // 앱은 `api/player/bundle` 과 `api/player/midi/<곡>` 두 가지만 부른다
  // (js/app.js 의 fetch 세 군데). 그 둘만 문서 안에서 꺼내 주고 나머지는
  // 원래 fetch 로 넘긴다.
  var realFetch = window.fetch ? window.fetch.bind(window) : null;

  function bytesOf(b64) {
    var bin = atob(b64), out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  window.fetch = function (input, init) {
    var url = String(input && input.url ? input.url : input);
    var path = url.split('?')[0];

    if (path.slice(-'api/player/bundle'.length) === 'api/player/bundle') {
      return Promise.resolve(new Response(JSON.stringify(MR_BUNDLE), {
        status: 200, headers: { 'Content-Type': 'application/json' } }));
    }

    var hit = path.match(/api\/player\/midi\/([^\/]+)$/);
    if (hit) {
      var name = decodeURIComponent(hit[1]);
      var b64 = MR_MIDI[name];
      if (!b64) {
        return Promise.resolve(new Response('없는 반주입니다: ' + name,
                                            { status: 404 }));
      }
      return Promise.resolve(new Response(bytesOf(b64), {
        status: 200, headers: { 'Content-Type': 'audio/midi' } }));
    }

    if (!realFetch) return Promise.reject(new Error('fetch 가 없습니다'));
    return realFetch(input, init);
  };

  // --- 모듈을 blob 으로 이어 붙인다 -------------------------------------------
  // `file://` 에서는 `<script type="module">` 의 상대경로 import 가 전부
  // 막힌다. 각 모듈을 blob 주소로 만들고 `'./engine.js'` 같은 지정자를 그
  // 주소로 바꿔치기하면 통째로 돈다. 앱 코드는 안 고친다.
  var urls = {};
  try {
    MR_ORDER.forEach(function (name) {
      var src = MR_SRC[name].replace(
        /(['"])\.\/([\w.\-]+\.js)\1/g,
        function (whole, q, dep) {
          if (!urls[dep]) throw new Error(name + ' 이(가) ' + dep +
                                          ' 보다 먼저 만들어졌습니다');
          return JSON.stringify(urls[dep]);
        });
      urls[name] = URL.createObjectURL(
        new Blob([src], { type: 'text/javascript' }));
    });
  } catch (e) {
    document.getElementById('view').textContent =
      '화면을 여는 데 실패했습니다: ' + e.message;
    return;
  }

  // 이 문서 안에 곡이 이미 다 들어 있다. 「오프라인 준비」는 할 일이 없다.
  var off = document.getElementById('offline');
  if (off) off.hidden = true;

  import(urls['app.js']).catch(function (e) {
    document.getElementById('view').textContent =
      '화면을 여는 데 실패했습니다: ' + e.message;
  });
})();
"""

PAGE = """<!doctype html>
<!-- 피아노학원 자동 반주 — 한 파일로 묶은 「들어보기」판.
     두 번 누르면 열립니다. 인터넷도, 파이썬도, 설치도 필요 없습니다.
     곡 {count}개가 이 문서 안에 들어 있습니다. -->
<html lang="ko" data-api="./">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0a090e">
<title>{title}</title>
<style>
{css}
</style>
</head>
<body>
{body}
<script>
var MR_BUNDLE = {bundle};
var MR_MIDI = {midi};
var MR_ORDER = {order};
var MR_SRC = {src};
{loader}
</script>
</body>
</html>
"""


def build(pkg, out, title='학원 반주 — 들어보기'):
    bundle, midi, src, css = collect(pkg)
    body = body_of(read_text(os.path.join(pkg, 'index.html')))

    html = PAGE.format(
        title=title,
        count=len(bundle.get('songs', [])),
        css=css,
        body=body,
        bundle=json.dumps(bundle, ensure_ascii=False),
        midi=json.dumps(midi),
        order=json.dumps(list(MODULES)),
        src=json.dumps(src, ensure_ascii=False),
        loader=LOADER,
    )
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    return {'out': out, 'songs': len(bundle.get('songs', [])),
            'variants': len(midi), 'bytes': os.path.getsize(out)}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='정적 꾸러미를 파일 하나로 묶는다 (두 번 눌러 여는 들어보기판)')
    ap.add_argument('package', help='catalog_cli.py package 로 만든 폴더')
    ap.add_argument('-o', '--out', default='들어보기.html')
    ap.add_argument('--title', default='학원 반주 — 들어보기')
    args = ap.parse_args(argv)

    try:
        info = build(args.package, args.out, args.title)
    except BuildError as e:
        print(e, file=sys.stderr)
        return 2

    print(f"  {info['out']}")
    print(f"  곡 {info['songs']}개 · 반주 {info['variants']}개 · "
          f"{info['bytes'] / 1024:.0f} KB")
    print('  두 번 누르면 브라우저에서 열립니다. 설치도 인터넷도 필요 없습니다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
