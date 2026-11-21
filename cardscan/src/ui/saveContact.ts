// 앱(안드로이드)은 연락처 연동이 자동이라 쓸 일이 없다 — 웹 전용 기능의 자리표시.
import { BusinessCard } from '../core/types';

export const CAN_OPEN_VCARD = false;

export function openVCard(_card: BusinessCard): void {}

export function exportAllVCards(_cards: BusinessCard[]): void {}
