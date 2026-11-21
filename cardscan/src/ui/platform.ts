// 플랫폼별 차이 — 웹(아이폰 홈 화면 웹앱)에서 자동 전송이 불가능한 연동을 등록한다.
import { Platform } from 'react-native';
import { setUnavailableConnectors } from '../core/settings';
import { ConnectorId } from '../core/types';

export const IS_WEB = Platform.OS === 'web';

/** 웹에서 막히는 연동과 이유 */
export const WEB_LIMITS: Partial<Record<ConnectorId, string>> = IS_WEB
  ? {
      contacts: '아이폰 웹앱은 연락처에 직접 저장할 수 없어, 명함마다 "아이폰 연락처에 저장" 버튼을 누르면 연락처 카드가 열립니다 → "새로운 연락처 생성".',
      hubspot: '아이폰 웹앱에서는 브라우저 보안 정책 때문에 HubSpot 으로 직접 보낼 수 없습니다. 웹훅(Zapier·Make)을 거쳐 연결하거나 안드로이드 앱을 쓰세요.',
      slack: '아이폰 웹앱에서는 브라우저 보안 정책 때문에 슬랙으로 직접 보낼 수 없습니다. 웹훅(Zapier·Make)을 거쳐 연결하세요.',
    }
  : {};

setUnavailableConnectors(Object.keys(WEB_LIMITS) as ConnectorId[]);
