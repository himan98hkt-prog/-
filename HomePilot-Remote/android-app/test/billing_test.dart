import 'package:flutter_test/flutter_test.dart';
import 'package:homepilot_remote/billing.dart';

void main() {
  test('제한을 켜지 않은 빌드(개발·시험)는 모든 기능이 열려 있다', () {
    expect(enforcePro, isFalse);
    expect(billing.isPro, isTrue);
  });

  test('상점 정보가 없을 때도 가격을 보여 준다', () {
    for (final id in allProducts) {
      expect(billing.priceOf(id), isNotEmpty);
    }
    expect(billing.priceOf(productLifetime), contains('39,000'));
  });
}
