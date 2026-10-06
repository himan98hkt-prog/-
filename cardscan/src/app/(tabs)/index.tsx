import { LinearGradient } from 'expo-linear-gradient';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, FlatList, Pressable, ScrollView, SectionList, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { allTags, dueFollowUps, filterCards, groupByCompany, SORT_LABEL, SortKey, stats, todayStr } from '../../core/organize';
import { connectorTargets } from '../../core/settings';
import { BusinessCard, CardKind, KIND_LABEL } from '../../core/types';
import { Avatar, Button, Icon, KindBadge, PressableScale, SyncDot, tap } from '../../ui/components';
import { useLightStatusBar } from '../../ui/statusBar';
import { useStore } from '../../ui/store';
import { FONT, gradientFor, RADIUS, shadow, T, type } from '../../ui/theme';

const KINDS: (CardKind | 'all')[] = ['all', 'customer', 'partner', 'other'];
const SORTS: SortKey[] = ['recent', 'name', 'company', 'updated'];

/** 처음 보일 때 아래에서 살짝 떠오르는 줄 */
function Rise({ index, children }: { index: number; children: React.ReactNode }) {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(v, { toValue: 1, duration: 360, delay: Math.min(index, 8) * 45, useNativeDriver: true }).start();
  }, [v, index]);
  return (
    <Animated.View style={{ opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [14, 0] }) }] }}>{children}</Animated.View>
  );
}

export default function CardListScreen() {
  const { cards, settings, ready, syncingIds, setMeta } = useStore();
  const insets = useSafeAreaInsets();
  useLightStatusBar();
  const params = useLocalSearchParams<{ tag?: string }>();
  const [query, setQuery] = useState('');
  const [kind, setKind] = useState<CardKind | 'all'>('all');
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [tag, setTag] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>('recent');
  const [byCompany, setByCompany] = useState(false);
  // 촬영 화면의 "확인필요 명함 보기" 등에서 그룹을 지정해 들어온 경우
  useEffect(() => {
    if (params.tag) setTag(params.tag);
  }, [params.tag]);

  const today = todayStr();
  const list = useMemo(() => filterCards(cards, { query, kind, favoritesOnly, tag, sort }), [cards, query, kind, favoritesOnly, tag, sort]);
  const tags = useMemo(() => allTags(cards), [cards]);
  const due = useMemo(() => dueFollowUps(cards, today), [cards, today]);
  const summary = useMemo(() => stats(cards, today), [cards, today]);
  const sections = useMemo(() => (byCompany ? groupByCompany(list).map((g) => ({ title: g.company, data: g.cards })) : []), [byCompany, list]);

  if (ready && cards.length === 0) {
    return (
      <LinearGradient colors={[T.ink, T.ink3]} style={[st.empty, { paddingTop: insets.top }]}>
        <View style={st.emptyMark}>
          <Icon name="scan" size={44} color={T.gold} />
        </View>
        <Text style={st.emptyTitle}>첫 명함을 찍어 보세요</Text>
        <Text style={st.emptySub}>찍는 순간 이름·회사·연락처를 읽어{'\n'}연락처와 업무 시스템에 자동으로 저장합니다.</Text>
        <Button title="명함 촬영 시작" icon="scan" variant="gold" onPress={() => router.navigate('/scan')} style={{ alignSelf: 'stretch', marginTop: 28 }} />
      </LinearGradient>
    );
  }

  const renderCard = ({ item, index }: { item: BusinessCard; index: number }) => {
    const targets = connectorTargets(settings, item.kind);
    const failed = targets.some((t) => item.sync[t]?.state === 'error');
    const overdue = item.followUp && item.followUp <= today;
    const [accent] = gradientFor(item.company || item.name);
    return (
      <Rise index={index}>
        <PressableScale style={st.row} onPress={() => router.push({ pathname: '/card/[id]', params: { id: item.id } })}>
          <View style={[st.rowAccent, { backgroundColor: accent }]} />
          <Avatar name={item.name || item.nameEn} company={item.company} size={50} favorite={item.favorite} />
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 6 }}>
              <Text style={st.name} numberOfLines={1}>
                {item.name || item.nameEn || '(이름 없음)'}
              </Text>
              <Text style={st.title} numberOfLines={1}>
                {item.title}
              </Text>
            </View>
            <Text style={st.company} numberOfLines={1}>
              {[item.company, item.department].filter(Boolean).join(' · ') || ' '}
            </Text>
            <View style={st.metaRow}>
              <KindBadge kind={item.kind} />
              {(item.tags ?? []).slice(0, 2).map((t) => (
                <Text key={t} style={st.tagMini}>#{t}</Text>
              ))}
              {item.followUp ? (
                <View style={[st.follow, overdue && { backgroundColor: T.errSoft }]}>
                  <Icon name="call" size={10} color={overdue ? T.err : T.goldDeep} />
                  <Text style={[st.followText, overdue && { color: T.err }]}>{item.followUp.slice(5).replace('-', '/')}</Text>
                </View>
              ) : null}
              <View style={{ flex: 1 }} />
              {syncingIds.has(item.id) ? <Text style={st.meta}>연동 중</Text> : failed ? <Icon name="alert-circle" size={14} color={T.err} /> : null}
              {targets.map((t) => (
                <SyncDot key={t} status={item.sync[t]} />
              ))}
            </View>
          </View>
          <Pressable
            hitSlop={14}
            onPress={() => {
              tap('select');
              setMeta(item.id, { favorite: !item.favorite });
            }}
            accessibilityLabel="즐겨찾기"
          >
            <Icon name={item.favorite ? 'star' : 'star-outline'} size={22} color={item.favorite ? T.gold : '#CBD2DE'} />
          </Pressable>
        </PressableScale>
      </Rise>
    );
  };

  const hero = (
    <LinearGradient colors={[T.ink, T.ink2, T.ink3]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[st.hero, { paddingTop: insets.top + 14 }]}>
      <View style={st.heroRing} />
      <View style={st.heroTop}>
        <View>
          <Text style={st.brand}>CARDSCAN</Text>
          <Text style={st.heroTitle}>명함첩</Text>
        </View>
        <Pressable onPress={() => router.push('/mycard')} style={st.myCardBtn} accessibilityLabel="내 명함">
          <Icon name="qr-code" size={18} color={T.gold} />
          <Text style={st.myCardText}>내 명함</Text>
        </Pressable>
      </View>
      <View style={st.statRow}>
        <Stat value={summary.total} label="전체" />
        <View style={st.statDiv} />
        <Stat value={`+${summary.thisMonth}`} label="이번 달" gold />
        <View style={st.statDiv} />
        <Stat value={summary.companies} label="회사" />
        <View style={st.statDiv} />
        <Stat value={summary.favorites} label="VIP" />
      </View>
      <View style={st.searchBox}>
        <Icon name="search" size={18} color="rgba(255,255,255,0.6)" />
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="이름·회사·번호·메모 (초성 ㅎㄱㄷ)"
          placeholderTextColor="rgba(255,255,255,0.45)"
          style={st.search}
        />
        {query ? (
          <Pressable onPress={() => setQuery('')} hitSlop={10}>
            <Icon name="close-circle" size={18} color="rgba(255,255,255,0.6)" />
          </Pressable>
        ) : null}
      </View>
    </LinearGradient>
  );

  const header = (
    <View>
      {hero}
      <View style={st.sheet}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={st.filters}>
          {KINDS.map((f) => {
            const count = f === 'all' ? cards.length : cards.filter((c) => c.kind === f).length;
            const on = kind === f;
            return (
              <Pressable key={f} onPress={() => { tap('select'); setKind(f); }} style={[st.chip, on && st.chipOn]}>
                <Text style={[st.chipText, on && { color: '#fff' }]}>
                  {f === 'all' ? '전체' : KIND_LABEL[f]} <Text style={[st.chipCount, on && { color: T.gold }]}>{count}</Text>
                </Text>
              </Pressable>
            );
          })}
          <Pressable onPress={() => { tap('select'); setFavoritesOnly((v) => !v); }} style={[st.chip, favoritesOnly && st.chipGold]}>
            <Icon name="star" size={13} color={favoritesOnly ? T.ink : T.gold} />
            <Text style={[st.chipText, favoritesOnly && { color: T.ink }]}> VIP</Text>
          </Pressable>
        </ScrollView>
        {tags.length ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={[st.filters, { paddingTop: 0 }]}>
            {tags.map(({ tag: t, count }) => {
              const on = tag === t;
              return (
                <Pressable key={t} onPress={() => { tap('select'); setTag(on ? null : t); }} style={[st.tagChip, on && st.chipOn]}>
                  <Text style={[st.tagChipText, on && { color: '#fff' }]}>#{t} {count}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
        ) : null}

        {due.length ? (
          <PressableScale onPress={() => router.push({ pathname: '/card/[id]', params: { id: due[0].id } })} style={{ marginHorizontal: 16, marginBottom: 12 }}>
            <LinearGradient colors={['#F7E7C3', '#E9CB8C']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[st.dueBox, shadow(1)]}>
              <View style={st.dueIcon}>
                <Icon name="call" size={20} color={T.gold} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={st.dueTitle}>오늘 연락할 사람 {due.length}명</Text>
                <Text style={st.dueSub} numberOfLines={1}>
                  {due.slice(0, 4).map((c) => `${c.name || c.company}${c.followUp! < today ? '(지남)' : ''}`).join(' · ')}
                </Text>
              </View>
              <Icon name="chevron-forward" size={18} color={T.ink} />
            </LinearGradient>
          </PressableScale>
        ) : null}

        <View style={st.toolRow}>
          <Pressable onPress={() => { tap('select'); setSort(SORTS[(SORTS.indexOf(sort) + 1) % SORTS.length]); }} style={st.tool}>
            <Icon name="swap-vertical" size={15} color={T.sub} />
            <Text style={st.toolText}>{SORT_LABEL[sort]}</Text>
          </Pressable>
          <Text style={st.resultCount}>{list.length}명</Text>
          <Pressable onPress={() => { tap('select'); setByCompany((v) => !v); }} style={st.tool}>
            <Icon name={byCompany ? 'people-outline' : 'business-outline'} size={15} color={T.sub} />
            <Text style={st.toolText}>{byCompany ? '사람별' : '회사별'}</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );

  const common = {
    keyExtractor: (c: BusinessCard) => c.id,
    contentContainerStyle: { paddingBottom: 40 },
    ListHeaderComponent: header,
    ItemSeparatorComponent: () => <View style={{ height: 10 }} />,
  };

  return (
    <View style={{ flex: 1, backgroundColor: T.bg }}>
      {byCompany ? (
        <SectionList
          {...common}
          sections={sections}
          renderSectionHeader={({ section }) => (
            <View style={st.sectionHeader}>
              <View style={[st.sectionDot, { backgroundColor: gradientFor(section.title)[1] }]} />
              <Text style={st.sectionTitle}>{section.title}</Text>
              <Text style={st.meta}>{section.data.length}명</Text>
            </View>
          )}
          renderItem={({ item, index }) => <View style={{ paddingHorizontal: 16 }}>{renderCard({ item, index })}</View>}
          stickySectionHeadersEnabled={false}
        />
      ) : (
        <FlatList
          {...common}
          data={list}
          ListEmptyComponent={<Text style={[st.emptyList]}>찾는 명함이 없습니다</Text>}
          renderItem={({ item, index }) => <View style={{ paddingHorizontal: 16 }}>{renderCard({ item, index })}</View>}
        />
      )}
    </View>
  );
}

function Stat({ value, label, gold }: { value: number | string; label: string; gold?: boolean }) {
  return (
    <View style={{ alignItems: 'center', flex: 1 }}>
      <Text style={[st.statValue, gold && { color: T.gold }]}>{value}</Text>
      <Text style={st.statLabel}>{label}</Text>
    </View>
  );
}

const st = StyleSheet.create({
  hero: { paddingHorizontal: 20, paddingBottom: 42, overflow: 'hidden' },
  heroRing: { position: 'absolute', width: 320, height: 320, borderRadius: 160, borderWidth: 1, borderColor: 'rgba(212,175,106,0.18)', right: -120, top: -140 },
  heroTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end' },
  brand: { fontFamily: FONT, fontSize: 11, fontWeight: '800', letterSpacing: 3, color: T.gold },
  heroTitle: { fontFamily: FONT, fontSize: 32, fontWeight: '800', color: '#fff', letterSpacing: -0.8, marginTop: 2 },
  myCardBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: 'rgba(212,175,106,0.5)', borderRadius: 18, paddingHorizontal: 12, paddingVertical: 7 },
  myCardText: { fontFamily: FONT, fontSize: 13, fontWeight: '700', color: T.gold },
  statRow: { flexDirection: 'row', alignItems: 'center', marginTop: 22, marginBottom: 18 },
  statValue: { fontFamily: FONT, fontSize: 22, fontWeight: '800', color: '#fff' },
  statLabel: { fontFamily: FONT, fontSize: 11, fontWeight: '600', color: 'rgba(255,255,255,0.55)', marginTop: 2 },
  statDiv: { width: 1, height: 26, backgroundColor: 'rgba(255,255,255,0.12)' },
  searchBox: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: RADIUS.md, paddingHorizontal: 14, borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)' },
  search: { flex: 1, fontFamily: FONT, fontSize: 15, color: '#fff', paddingVertical: 12 },
  sheet: { marginTop: -24, backgroundColor: T.bg, borderTopLeftRadius: 26, borderTopRightRadius: 26, paddingTop: 8, marginBottom: 4 },
  filters: { flexDirection: 'row', gap: 8, paddingHorizontal: 16, paddingVertical: 10 },
  chip: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 18, backgroundColor: '#fff', ...shadow(1) },
  chipOn: { backgroundColor: T.ink },
  chipGold: { backgroundColor: T.gold },
  chipText: { ...type(13, '700'), lineHeight: 17 },
  chipCount: { ...type(13, '700', T.faint), lineHeight: 17 },
  tagChip: { paddingHorizontal: 11, paddingVertical: 6, borderRadius: 14, backgroundColor: '#E9ECF6' },
  tagChipText: { ...type(12, '700', T.ink3), lineHeight: 16 },
  dueBox: { flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: RADIUS.lg, padding: 14 },
  dueIcon: { width: 40, height: 40, borderRadius: 20, backgroundColor: T.ink, alignItems: 'center', justifyContent: 'center' },
  dueTitle: { ...type(16, '800', T.ink) },
  dueSub: { ...type(13, '600', '#5A4A2A') },
  toolRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 20, paddingBottom: 8 },
  tool: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 4 },
  toolText: { ...type(13, '700', T.sub) },
  resultCount: { ...type(12, '600', T.faint) },
  row: { flexDirection: 'row', gap: 14, backgroundColor: '#fff', borderRadius: RADIUS.lg, padding: 14, paddingLeft: 16, alignItems: 'center', overflow: 'hidden', ...shadow(1) },
  rowAccent: { position: 'absolute', left: 0, top: 14, bottom: 14, width: 3, borderTopRightRadius: 3, borderBottomRightRadius: 3 },
  name: { ...type(17, '800'), flexShrink: 1 },
  title: { ...type(13, '600', T.sub) },
  company: { ...type(14, '500', '#3A4256'), marginTop: 1 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6 },
  meta: { ...type(12, '600', T.faint) },
  tagMini: { ...type(11, '700', T.ink3) },
  follow: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: T.goldSoft, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1 },
  followText: { ...type(11, '800', T.goldDeep), lineHeight: 15 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 20, marginTop: 14, marginBottom: 8 },
  sectionDot: { width: 10, height: 10, borderRadius: 3 },
  sectionTitle: { ...type(15, '800') },
  emptyList: { ...type(15, '600', T.sub), textAlign: 'center', marginTop: 40 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  emptyMark: { width: 96, height: 96, borderRadius: 30, borderWidth: 1.5, borderColor: 'rgba(212,175,106,0.6)', alignItems: 'center', justifyContent: 'center', marginBottom: 24 },
  emptyTitle: { ...type(24, '800', '#fff') },
  emptySub: { ...type(15, '500', 'rgba(255,255,255,0.65)'), textAlign: 'center', marginTop: 10, lineHeight: 23 },
});
