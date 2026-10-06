import { Link, router, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { FlatList, Pressable, ScrollView, SectionList, StyleSheet, Text, TextInput, View } from 'react-native';
import { allTags, dueFollowUps, filterCards, groupByCompany, SORT_LABEL, SortKey, stats, todayStr } from '../../core/organize';
import { connectorTargets } from '../../core/settings';
import { BusinessCard, CardKind, KIND_LABEL } from '../../core/types';
import { CardImage } from '../../ui/CardImage';
import { Button, C, KindBadge, SyncDot } from '../../ui/components';
import { useStore } from '../../ui/store';

const KINDS: (CardKind | 'all')[] = ['all', 'customer', 'partner', 'other'];
const SORTS: SortKey[] = ['recent', 'name', 'company', 'updated'];

export default function CardListScreen() {
  const { cards, settings, ready, syncingIds, setMeta } = useStore();
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
      <View style={st.empty}>
        <Text style={st.emptyTitle}>아직 저장된 명함이 없습니다</Text>
        <Text style={st.emptySub}>명함을 찍으면 이름·회사·연락처를 읽어{'\n'}휴대폰 연락처와 연동 시스템에 자동으로 저장합니다.</Text>
        <Button title="첫 명함 촬영하기" onPress={() => router.navigate('/scan')} style={{ alignSelf: 'stretch', marginTop: 24 }} />
      </View>
    );
  }

  const renderCard = ({ item }: { item: BusinessCard }) => {
    const targets = connectorTargets(settings, item.kind);
    const failed = targets.some((t) => item.sync[t]?.state === 'error');
    const overdue = item.followUp && item.followUp <= today;
    return (
      <Link href={{ pathname: '/card/[id]', params: { id: item.id } }} asChild>
        <Pressable style={st.row}>
          <CardImage uri={item.imageUri} style={st.thumb} />
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <Text style={st.name} numberOfLines={1}>
                {item.name || item.nameEn || '(이름 없음)'}
              </Text>
              <Text style={st.title} numberOfLines={1}>
                {item.title}
              </Text>
            </View>
            <Text style={st.company} numberOfLines={1}>
              {[item.company, item.department].filter(Boolean).join(' · ')}
            </Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
              <KindBadge kind={item.kind} />
              {(item.tags ?? []).slice(0, 2).map((t) => (
                <Text key={t} style={st.tagMini}>#{t}</Text>
              ))}
              {item.followUp ? <Text style={[st.meta, overdue && { color: C.err, fontWeight: '700' }]}>📞 {item.followUp.slice(5)}</Text> : null}
              {targets.map((t) => (
                <SyncDot key={t} status={item.sync[t]} />
              ))}
              {syncingIds.has(item.id) ? <Text style={st.meta}>연동 중…</Text> : failed ? <Text style={[st.meta, { color: C.err }]}>연동 실패</Text> : null}
            </View>
          </View>
          <Pressable hitSlop={12} onPress={() => setMeta(item.id, { favorite: !item.favorite })} accessibilityLabel="즐겨찾기">
            <Text style={[st.star, item.favorite && { color: '#F5A524' }]}>{item.favorite ? '★' : '☆'}</Text>
          </Pressable>
        </Pressable>
      </Link>
    );
  };

  const header = (
    <View>
      {due.length ? (
        <Pressable style={st.dueBox} onPress={() => router.push({ pathname: '/card/[id]', params: { id: due[0].id } })}>
          <Text style={st.dueTitle}>📞 오늘 연락할 사람 {due.length}명</Text>
          <Text style={st.dueSub} numberOfLines={2}>
            {due.slice(0, 5).map((c) => `${c.name || c.company}${c.followUp! < today ? '(지남)' : ''}`).join(', ')}
          </Text>
        </Pressable>
      ) : null}
      <Text style={st.summary}>
        전체 {summary.total}명 · 이번 달 +{summary.thisMonth} · 회사 {summary.companies}곳{summary.favorites ? ` · ★ ${summary.favorites}` : ''}
      </Text>
    </View>
  );

  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <View style={st.top}>
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="이름·회사·번호·메모 검색 (초성 ㅎㄱㄷ 가능)"
          placeholderTextColor="#9CA3AF"
          style={st.search}
          clearButtonMode="while-editing"
        />
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={st.filters}>
          {KINDS.map((f) => {
            const count = f === 'all' ? cards.length : cards.filter((c) => c.kind === f).length;
            const on = kind === f;
            return (
              <Pressable key={f} onPress={() => setKind(f)} style={[st.chip, on && st.chipOn]}>
                <Text style={[st.chipText, on && { color: '#fff' }]}>
                  {f === 'all' ? '전체' : KIND_LABEL[f]} {count}
                </Text>
              </Pressable>
            );
          })}
          <Pressable onPress={() => setFavoritesOnly((v) => !v)} style={[st.chip, favoritesOnly && st.chipStar]}>
            <Text style={[st.chipText, favoritesOnly && { color: '#fff' }]}>★ 즐겨찾기</Text>
          </Pressable>
        </ScrollView>
        {tags.length ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={[st.filters, { marginTop: 6 }]}>
            {tags.map(({ tag: t, count }) => {
              const on = tag === t;
              return (
                <Pressable key={t} onPress={() => setTag(on ? null : t)} style={[st.chipSm, on && st.chipOn]}>
                  <Text style={[st.chipSmText, on && { color: '#fff' }]}>#{t} {count}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
        ) : null}
        <View style={st.toolRow}>
          <Pressable onPress={() => setSort(SORTS[(SORTS.indexOf(sort) + 1) % SORTS.length])}>
            <Text style={st.tool}>↕ {SORT_LABEL[sort]}</Text>
          </Pressable>
          <Pressable onPress={() => setByCompany((v) => !v)}>
            <Text style={st.tool}>{byCompany ? '👤 사람별 보기' : '🏢 회사별 보기'}</Text>
          </Pressable>
        </View>
      </View>
      {byCompany ? (
        <SectionList
          sections={sections}
          keyExtractor={(c) => c.id}
          contentContainerStyle={{ padding: 12, paddingBottom: 96 }}
          ListHeaderComponent={header}
          renderSectionHeader={({ section }) => (
            <Text style={st.sectionHeader}>
              🏢 {section.title} <Text style={st.meta}>{section.data.length}명</Text>
            </Text>
          )}
          ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
          renderItem={renderCard}
          stickySectionHeadersEnabled={false}
        />
      ) : (
        <FlatList
          data={list}
          keyExtractor={(c) => c.id}
          contentContainerStyle={{ padding: 12, paddingBottom: 96 }}
          ListHeaderComponent={header}
          ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
          ListEmptyComponent={<Text style={[st.emptySub, { marginTop: 40 }]}>검색 결과가 없습니다</Text>}
          renderItem={renderCard}
        />
      )}
      <Pressable style={st.fab} onPress={() => router.navigate('/scan')} accessibilityLabel="명함 촬영">
        <Text style={st.fabText}>＋ 명함 촬영</Text>
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  top: { padding: 12, paddingBottom: 4, backgroundColor: C.bg },
  search: { backgroundColor: '#fff', borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, borderWidth: 1, borderColor: C.line },
  filters: { flexDirection: 'row', gap: 6, marginTop: 10 },
  chip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16, backgroundColor: '#fff', borderWidth: 1, borderColor: C.line },
  chipOn: { backgroundColor: C.text, borderColor: C.text },
  chipStar: { backgroundColor: '#F5A524', borderColor: '#F5A524' },
  chipText: { fontSize: 13, fontWeight: '600', color: C.text },
  chipSm: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14, backgroundColor: '#EEF2FF' },
  chipSmText: { fontSize: 12, fontWeight: '600', color: '#4338CA' },
  toolRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8, paddingHorizontal: 2 },
  tool: { fontSize: 13, color: C.primary, fontWeight: '600', paddingVertical: 4 },
  row: { flexDirection: 'row', gap: 12, backgroundColor: '#fff', borderRadius: 14, padding: 12, alignItems: 'center' },
  thumb: { width: 72, height: 44, borderRadius: 6 },
  name: { fontSize: 17, fontWeight: '700', color: C.text, flexShrink: 1 },
  title: { fontSize: 13, color: C.sub },
  company: { fontSize: 14, color: C.text, marginTop: 2 },
  meta: { fontSize: 12, color: C.sub },
  tagMini: { fontSize: 11, color: '#4338CA' },
  star: { fontSize: 24, color: '#CBD5E1', paddingHorizontal: 4 },
  dueBox: { backgroundColor: '#FFF7ED', borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: '#FED7AA' },
  dueTitle: { fontSize: 16, fontWeight: '700', color: '#9A3412' },
  dueSub: { fontSize: 13, color: '#9A3412', marginTop: 4 },
  summary: { fontSize: 12, color: C.sub, marginBottom: 8, marginLeft: 2 },
  sectionHeader: { fontSize: 15, fontWeight: '700', color: C.text, marginTop: 12, marginBottom: 8, marginLeft: 2 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, backgroundColor: C.bg },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: C.text },
  emptySub: { fontSize: 15, color: C.sub, textAlign: 'center', marginTop: 8, lineHeight: 22 },
  fab: { position: 'absolute', right: 16, bottom: 20, backgroundColor: C.primary, borderRadius: 28, paddingHorizontal: 22, paddingVertical: 16, elevation: 4, shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 8, shadowOffset: { width: 0, height: 3 } },
  fabText: { color: '#fff', fontSize: 16, fontWeight: '700' },
});
