import 'dart:ui';

/// 원격 화면 표시 영역 계산: 화면 맞춤(contain) + 확대/이동, 터치 좌표 → PC 비율 좌표.
///
/// 좌표 모델: 화면 좌표 = (확대 전 좌표) × scale + translate
class ViewTransform {
  double scale = 1;
  Offset translate = Offset.zero;

  void reset() {
    scale = 1;
    translate = Offset.zero;
  }

  /// 확대 전, 화면에 맞춘 이미지 영역.
  static Rect fitted(Size box, Size frame) {
    final sx = box.width / frame.width, sy = box.height / frame.height;
    final s = sx < sy ? sx : sy;
    final w = frame.width * s, h = frame.height * s;
    return Rect.fromLTWH((box.width - w) / 2, (box.height - h) / 2, w, h);
  }

  /// 현재 확대/이동이 적용된 이미지 영역.
  Rect imageRect(Size box, Size frame) {
    final f = fitted(box, frame);
    return Rect.fromLTWH(f.left * scale + translate.dx, f.top * scale + translate.dy, f.width * scale, f.height * scale);
  }

  /// 두 손가락 확대: 처음 손가락 중심 아래의 점이 손가락을 따라가도록.
  void zoom(double startScale, double gestureScale, Offset focalStart, Offset focalNow, Offset translateStart, Size box) {
    final ns = (startScale * gestureScale).clamp(1.0, 6.0);
    final base = (focalStart - translateStart) / startScale;
    scale = ns;
    translate = focalNow - base * ns;
    // 확대된 내용이 화면 밖으로 빠져나가지 않게
    translate = Offset(translate.dx.clamp(box.width - box.width * ns, 0.0), translate.dy.clamp(box.height - box.height * ns, 0.0));
  }

  /// 화면 좌표 → PC 화면 비율 좌표(0~1). 이미지 밖이면 null.
  Offset? toNormalized(Offset p, Size box, Size frame) {
    final r = imageRect(box, frame);
    if (!r.contains(p)) return null;
    return Offset(((p.dx - r.left) / r.width).clamp(0.0, 1.0), ((p.dy - r.top) / r.height).clamp(0.0, 1.0));
  }
}
