import Constants from 'expo-constants';
import React, { useState } from 'react';
import { Alert, Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { isConfigured } from '../../api';
import { deleteAccount } from '../../api/supabase';
import { PET_LABEL } from '../../core/emotions';
import { PRO_PRICE_KRW } from '../../core/quota';
import { usePetStore, useIsPro, useQuota } from '../../store/usePetStore';
import { Badge, Button, Card, SectionTitle } from '../components/Basics';
import { LINKS } from '../links';
import { useNavigation } from '../navigation';
import { colors, font, radius, space } from '../theme';

export function SettingsScreen() {
  const nav = useNavigation();
  const pets = usePetStore((s) => s.pets);
  const removePet = usePetStore((s) => s.removePet);
  const resetAll = usePetStore((s) => s.resetAll);
  const entries = usePetStore((s) => s.entries);
  const isPro = useIsPro();
  const quota = useQuota();
  const [deleting, setDeleting] = useState(false);

  /** Play 정책: 로그인 없는 로컬 앱은 "모든 데이터 초기화"를 반드시 제공해야 한다. */
  const confirmReset = () => {
    Alert.alert(
      '모든 데이터를 지울까요?',
      `등록한 반려동물 ${pets.length}마리와 분석 기록 ${entries.length}건이 기기에서 완전히 삭제됩니다. 되돌릴 수 없어요.`,
      [
        { text: '취소', style: 'cancel' },
        {
          text: '전부 삭제',
          style: 'destructive',
          onPress: () => {
            resetAll();
            Alert.alert('삭제했어요', '모든 데이터가 지워졌습니다.');
            nav.switchTab('home');
          },
        },
      ],
    );
  };

  /** Play 정책: 계정을 만드는 앱은 앱 안에서 계정 삭제를 제공해야 한다. */
  const confirmAccountDelete = () => {
    Alert.alert(
      '계정과 서버 데이터를 삭제할까요?',
      '익명 계정과 서버에 저장된 사용 기록이 모두 삭제됩니다. 기기 안의 기록도 함께 지워집니다.',
      [
        { text: '취소', style: 'cancel' },
        {
          text: '계정 삭제',
          style: 'destructive',
          onPress: async () => {
            setDeleting(true);
            try {
              await deleteAccount();
              resetAll();
              Alert.alert('삭제 완료', '계정과 데이터가 삭제됐습니다.');
              nav.switchTab('home');
            } catch {
              Alert.alert('삭제 실패', '네트워크를 확인한 뒤 다시 시도해 주세요.');
            } finally {
              setDeleting(false);
            }
          },
        },
      ],
    );
  };

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={font.h1}>설정</Text>

      <Card style={{ gap: space.md }}>
        <SectionTitle right={<Badge text={isPro ? 'PRO' : 'FREE'} bg={isPro ? colors.proSoft : colors.surfaceAlt} fg={isPro ? colors.pro : colors.textSoft} />}>
          구독
        </SectionTitle>
        <Text style={font.body}>{quota.label}</Text>
        {!isPro ? (
          <Button label={`프로 구독하기 · 월 ${PRO_PRICE_KRW.toLocaleString('ko-KR')}원`} variant="pro" onPress={() => nav.navigate('paywall')} />
        ) : null}
      </Card>

      <Card style={{ gap: space.md }}>
        <SectionTitle
          right={
            <Pressable accessibilityRole="button" onPress={() => nav.navigate('petForm')}>
              <Text style={[font.small, { color: colors.primaryDark }]}>+ 추가</Text>
            </Pressable>
          }
        >
          내 반려동물
        </SectionTitle>
        {pets.length === 0 ? (
          <Text style={[font.small, { color: colors.textSoft }]}>등록된 아이가 없어요.</Text>
        ) : (
          pets.map((pet) => (
            <View key={pet.id} style={styles.petRow}>
              <View style={{ flex: 1 }}>
                <Text style={font.bodyStrong}>{pet.name}</Text>
                <Text style={[font.tiny, { color: colors.textFaint }]}>
                  {PET_LABEL[pet.type]}
                  {pet.breed ? ` · ${pet.breed}` : ''}
                </Text>
              </View>
              <Pressable accessibilityRole="button" onPress={() => nav.navigate('petForm', { petId: pet.id })} hitSlop={8}>
                <Text style={[font.small, { color: colors.primaryDark }]}>수정</Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                hitSlop={8}
                onPress={() =>
                  Alert.alert(`${pet.name} 프로필을 삭제할까요?`, '이 아이의 분석 기록도 함께 사라집니다.', [
                    { text: '취소', style: 'cancel' },
                    { text: '삭제', style: 'destructive', onPress: () => removePet(pet.id) },
                  ])
                }
              >
                <Text style={[font.small, { color: colors.danger }]}>삭제</Text>
              </Pressable>
            </View>
          ))
        )}
      </Card>

      <Card style={{ gap: space.md }}>
        <SectionTitle>개인정보 및 데이터</SectionTitle>
        <LinkRow label="개인정보처리방침" onPress={() => void Linking.openURL(LINKS.privacy)} />
        <LinkRow label="이용약관" onPress={() => void Linking.openURL(LINKS.terms)} />
        <LinkRow label="문의하기" onPress={() => void Linking.openURL(LINKS.support)} />
        <Button label="모든 데이터 초기화" variant="danger" onPress={confirmReset} />
        {isConfigured ? (
          <Button label="계정 삭제" variant="danger" loading={deleting} onPress={confirmAccountDelete} />
        ) : null}
      </Card>

      <Card style={{ gap: space.sm }}>
        <SectionTitle>앱 정보</SectionTitle>
        <Row label="버전" value={String(Constants.expoConfig?.version ?? '1.0.0')} />
        <Row label="분석 서버" value={isConfigured ? '연결됨' : '데모 모드'} />
        <Text style={[font.tiny, { color: colors.textFaint, marginTop: space.sm }]}>
          PetVoice AI 의 분석 결과는 참고용이며 수의학적 진단을 대체하지 않습니다.
        </Text>
      </Card>
    </ScrollView>
  );
}

function LinkRow({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="link" onPress={onPress} style={styles.linkRow}>
      <Text style={font.body}>{label}</Text>
      <Text style={{ color: colors.textFaint }}>›</Text>
    </Pressable>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.linkRow}>
      <Text style={[font.small, { color: colors.textSoft }]}>{label}</Text>
      <Text style={font.small}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
  petRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.lg,
    paddingVertical: space.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  linkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: space.sm,
    borderRadius: radius.sm,
  },
});
