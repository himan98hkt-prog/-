import { Tabs } from 'expo-router/tabs';
import { ColorValue, Text } from 'react-native';
import { C } from '../../ui/components';

const icon = (glyph: string) =>
  function TabIcon({ color }: { color: ColorValue }) {
    return <Text style={{ fontSize: 20, color }}>{glyph}</Text>;
  };

export default function TabsLayout() {
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: C.primary, headerTitleStyle: { fontWeight: '700' } }}>
      <Tabs.Screen name="index" options={{ title: '명함첩', tabBarIcon: icon('▤') }} />
      <Tabs.Screen name="scan" options={{ title: '명함 촬영', tabBarIcon: icon('◉') }} />
      <Tabs.Screen name="settings" options={{ title: '설정·연동', tabBarIcon: icon('⚙') }} />
    </Tabs>
  );
}
