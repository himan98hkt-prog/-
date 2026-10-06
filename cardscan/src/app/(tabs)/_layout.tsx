import { LinearGradient } from 'expo-linear-gradient';
import { t } from '../../i18n';
import { Tabs } from 'expo-router/tabs';
import { ColorValue, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icon, IconName, tap } from '../../ui/components';
import { FONT, shadow, T } from '../../ui/theme';

const icon = (on: IconName, off: IconName) =>
  function TabIcon({ focused, color }: { focused: boolean; color: ColorValue }) {
    return <Icon name={focused ? on : off} size={23} color={String(color)} />;
  };

export default function TabsLayout() {
  // 안드로이드 화면 하단 3버튼·제스처 바 높이만큼 탭바를 올린다
  const bottom = useSafeAreaInsets().bottom;
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: T.ink,
        tabBarInactiveTintColor: T.faint,
        tabBarStyle: [st.bar, { height: 66 + bottom, paddingBottom: 8 + bottom }],
        tabBarLabelStyle: st.label,
        headerTitleStyle: { fontFamily: FONT, fontWeight: '800', fontSize: 19, color: T.text },
        headerShadowVisible: false,
        headerStyle: { backgroundColor: T.bg },
      }}
      screenListeners={{ tabPress: () => tap('select') }}
    >
      <Tabs.Screen name="index" options={{ title: t('명함첩'), headerShown: false, tabBarIcon: icon('albums', 'albums-outline') }} />
      <Tabs.Screen
        name="scan"
        options={{
          title: t('촬영'),
          headerShown: false,
          tabBarLabel: () => null,
          // 가운데 금테 원형 촬영 버튼 — 이 앱의 핵심 동작을 늘 한가운데에
          tabBarButton: ({ onPress, accessibilityState }) => (
            <Pressable onPress={onPress} style={st.centerWrap} accessibilityRole="button" accessibilityLabel={t('명함 촬영')}>
              <View style={[st.centerRing, accessibilityState?.selected && { borderColor: T.gold }]}>
                <LinearGradient colors={[T.ink3, T.ink]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={st.center}>
                  <Icon name="scan" size={28} color={T.gold} />
                </LinearGradient>
              </View>
            </Pressable>
          ),
        }}
      />
      <Tabs.Screen name="settings" options={{ title: t('설정·연동'), tabBarIcon: icon('options', 'options-outline') }} />
    </Tabs>
  );
}

const st = StyleSheet.create({
  bar: { height: 66, paddingTop: 6, paddingBottom: 8, borderTopWidth: 0, backgroundColor: '#fff', ...shadow(2) },
  label: { fontFamily: FONT, fontSize: 11, fontWeight: '700' },
  centerWrap: { flex: 1, alignItems: 'center', justifyContent: 'flex-start' },
  centerRing: { marginTop: -26, padding: 4, borderRadius: 40, backgroundColor: '#fff', borderWidth: 2, borderColor: 'rgba(212,175,106,0.55)', ...shadow(2) },
  center: { width: 62, height: 62, borderRadius: 31, alignItems: 'center', justifyContent: 'center' },
});
