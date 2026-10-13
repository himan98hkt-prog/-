import 'package:flutter_test/flutter_test.dart';
import 'package:homepilot_remote/protocol/directory.dart';

// Rust shared/protocol/src/directory.rs 의 cross_language_vector 와 같은 값
const vector =
    'AQEBAQEBAQEBAQEBCYoeg8yemWunMkEbDq9MeLTrh3fG1uhJ2ciurHDdFpoZ3IxrJZ4BBZXfksvIBgP5UVbf8aTjtlJmCiuV7-r8Jjah37TXiddrbH2tQ5VanShfNDJ65rL0B7yuMz-P-r2OLWqDmqguwDEU6EOtYRGCn0OLenNfNFvNZKrUiYVkyUuC3yM8';
final pk = List<int>.filled(32, 7);

void main() {
  test('주제 이름이 Rust 와 같다', () {
    expect(directoryTopic(pk), 'hp2d1b264484501029dce89e607a5056');
  });

  test('Rust 가 만든 기록을 연다', () async {
    final r = await openRecord(pk, vector);
    expect(r, isNotNull);
    expect(r!.id, 'f685fa3773a954e5b5a1');
    expect(r.url, 'https://a-b.trycloudflare.com');
    expect(r.lan, ['192.168.0.5:8443']);
    expect(r.ts, 1700000000);
  });

  test('다른 PC 키·손상된 기록은 거부', () async {
    expect(await openRecord(List<int>.filled(32, 8), vector), isNull);
    expect(await openRecord(pk, '${vector.substring(0, vector.length - 2)}AA'), isNull);
    expect(await openRecord(pk, 'not-base64!!'), isNull);
  });
}
