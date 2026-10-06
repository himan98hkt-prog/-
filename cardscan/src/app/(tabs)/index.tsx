import { Link, router } from 'expo-router';
import { useMemo, useState } from 'react';
import { FlatList, Image, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { filterCards } from '../../core/mapping';
import { connectorTargets } from '../../core/settings';
import { CardKind, KIND_LABEL } from '../../core/types';
import { Button, C, KindBadge, SyncDot } from '../../ui/components';
import { useStore } from '../../ui/store';

const FILTERS: (CardKind | 'all')[] = ['all', 'customer', 'partner', 'other'];

export default function CardListScreen() {
  const { cards, settings, ready, syncingIds } = useStore();
  const [query, setQuery] = useState('');
  const [kind, setKind] = useState<CardKind | 'all'>('all');
  const list = useMemo(() => filterCards(cards, query, kind), [cards, query, kind]);

  if (ready && cards.length === 0) {
    return (
      <View style={st.empty}>
        <Text style={st.emptyTitle}>아직 저장된 명함이 없습니다</Text>
        <Text style={st.emptySub}>명함을 찍으면 이름·회사·연락처를 읽어{'\n'}휴대폰 연락처와 연동 시스템에 자동으로 저장합니다.</Text>
        <Button title="첫 명함 촬영하기" onPress={() => router.navigate('/scan')} style={{ alignSelf: 'stretch', marginTop: 24 }} />
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <View style={st.top}>
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="이름·회사·번호·이메일 검색"
          placeholderTextColor="#9CA3AF"
          style={st.search}
          clearButtonMode="while-editing"
        />
        <View style={st.filters}>
          {FILTERS.map((f) => {
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
        </View>
      </View>
      <FlatList
        data={list}
        keyExtractor={(c) => c.id}
        contentContainerStyle={{ padding: 12, paddingBottom: 96 }}
        ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
        ListEmptyComponent={<Text style={[st.emptySub, { marginTop: 40 }]}>검색 결과가 없습니다</Text>}
        renderItem={({ item }) => {
          const targets = connectorTargets(settings, item.kind);
          const failed = targets.some((t) => item.sync[t]?.state === 'error');
          return (
            <Link href={{ pathname: '/card/[id]', params: { id: item.id } }} asChild>
              <Pressable style={st.row}>
                {item.imageUri ? <Image source={{ uri: item.imageUri }} style={st.thumb} /> : <View style={[st.thumb, { backgroundColor: C.line }]} />}
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
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 }}>
                    <KindBadge kind={item.kind} />
                    {targets.map((t) => (
                      <SyncDot key={t} status={item.sync[t]} />
                    ))}
                    {syncingIds.has(item.id) ? <Text style={st.meta}>연동 중…</Text> : failed ? <Text style={[st.meta, { color: C.err }]}>연동 실패</Text> : null}
                  </View>
                </View>
              </Pressable>
            </Link>
          );
        }}
      />
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
  chipText: { fontSize: 13, fontWeight: '600', color: C.text },
  row: { flexDirection: 'row', gap: 12, backgroundColor: '#fff', borderRadius: 14, padding: 12, alignItems: 'center' },
  thumb: { width: 72, height: 44, borderRadius: 6 },
  name: { fontSize: 17, fontWeight: '700', color: C.text, flexShrink: 1 },
  title: { fontSize: 13, color: C.sub },
  company: { fontSize: 14, color: C.text, marginTop: 2 },
  meta: { fontSize: 12, color: C.sub },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, backgroundColor: C.bg },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: C.text },
  emptySub: { fontSize: 15, color: C.sub, textAlign: 'center', marginTop: 8, lineHeight: 22 },
  fab: { position: 'absolute', right: 16, bottom: 20, backgroundColor: C.primary, borderRadius: 28, paddingHorizontal: 22, paddingVertical: 16, elevation: 4, shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 8, shadowOffset: { width: 0, height: 3 } },
  fabText: { color: '#fff', fontSize: 16, fontWeight: '700' },
});
