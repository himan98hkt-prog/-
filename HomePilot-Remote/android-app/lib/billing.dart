// 유료 기능(Pro) — Google Play 결제.
//
// 가격은 Play Console 에서 정한다 (아래 기본 표시 가격은 상점 정보를 못 받았을 때만 사용).
// 무료: PC 1대, 원격 화면·조작(절약/보통 화질), 파일, 클립보드, 자동 연결
// Pro : PC 무제한, 선명 화질(원본·30fps), PC 소리, AI 작업 관리
//
// 제한 적용은 빌드 옵션으로 켠다: flutter build appbundle --dart-define=ENFORCE_PRO=true
// (개발·시험 APK 는 모든 기능이 열려 있다)

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:shared_preferences/shared_preferences.dart';

const enforcePro = bool.fromEnvironment('ENFORCE_PRO');

/// Play Console 에 같은 ID 로 상품을 만든다.
const productMonthly = 'homepilot_pro_monthly'; // 구독
const productYearly = 'homepilot_pro_yearly'; // 구독
const productLifetime = 'homepilot_pro_lifetime'; // 일회성(관리형) 상품
const allProducts = {productMonthly, productYearly, productLifetime};

/// 상점 정보를 못 받았을 때 보여 줄 가격
const fallbackPrices = {productMonthly: '₩1,900 / 월', productYearly: '₩14,900 / 년', productLifetime: '₩39,000 (한 번 결제)'};

class Billing extends ChangeNotifier {
  // 처음 쓸 때 연결 (테스트·상점 없는 기기에서 앱 시작을 막지 않도록)
  InAppPurchase get _iap => InAppPurchase.instance;
  StreamSubscription<List<PurchaseDetails>>? _sub;
  bool available = false;
  Map<String, ProductDetails> products = {};
  bool _pro = false;
  String? lastError;
  bool busy = false;

  /// Pro 기능을 쓸 수 있는지 (제한을 켜지 않은 빌드는 항상 true)
  bool get isPro => !enforcePro || _pro;

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _pro = prefs.getBool('pro') ?? false;
    try {
      available = await _iap.isAvailable();
    } catch (_) {
      available = false;
    }
    if (!available) return;
    _sub = _iap.purchaseStream.listen(_onPurchases, onError: (Object e) {
      lastError = '$e';
      notifyListeners();
    });
    final r = await _iap.queryProductDetails(allProducts);
    products = {for (final p in r.productDetails) p.id: p};
    // 다른 기기·재설치 후에도 구매 상태를 되살린다
    await _iap.restorePurchases();
    notifyListeners();
  }

  String priceOf(String id) => products[id]?.price ?? fallbackPrices[id] ?? '';

  Future<void> buy(String id) async {
    final p = products[id];
    if (p == null) {
      lastError = '상점에서 상품 정보를 받지 못했습니다. Google Play 에서 설치한 앱인지 확인하세요.';
      notifyListeners();
      return;
    }
    busy = true;
    lastError = null;
    notifyListeners();
    final param = PurchaseParam(productDetails: p);
    try {
      // 구독·평생 모두 소모되지 않는 상품
      await _iap.buyNonConsumable(purchaseParam: param);
    } catch (e) {
      busy = false;
      lastError = '$e';
      notifyListeners();
    }
  }

  Future<void> restore() async {
    if (available) await _iap.restorePurchases();
  }

  Future<void> _onPurchases(List<PurchaseDetails> list) async {
    for (final p in list) {
      switch (p.status) {
        case PurchaseStatus.purchased || PurchaseStatus.restored:
          if (allProducts.contains(p.productID)) await _setPro(true);
        case PurchaseStatus.error:
          lastError = p.error?.message ?? '결제 오류';
        case PurchaseStatus.canceled || PurchaseStatus.pending:
          break;
      }
      if (p.pendingCompletePurchase) await _iap.completePurchase(p);
    }
    busy = false;
    notifyListeners();
  }

  Future<void> _setPro(bool v) async {
    _pro = v;
    (await SharedPreferences.getInstance()).setBool('pro', v);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}

final billing = Billing();
