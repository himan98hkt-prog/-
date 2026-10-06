import { CardFields, FIELD_LABEL } from '../core/types';
import { Field } from './components';

const ORDER: (keyof CardFields)[] = [
  'name', 'company', 'department', 'title', 'mobile', 'phone', 'fax', 'email', 'website', 'address', 'nameEn', 'memo',
];

const KEYBOARD: Partial<Record<keyof CardFields, 'phone-pad' | 'email-address' | 'url'>> = {
  mobile: 'phone-pad',
  phone: 'phone-pad',
  fax: 'phone-pad',
  email: 'email-address',
  website: 'url',
};

export function CardForm({ value, onChange }: { value: CardFields; onChange: (v: CardFields) => void }) {
  return (
    <>
      {ORDER.map((k) => (
        <Field
          key={k}
          label={FIELD_LABEL[k]}
          value={value[k]}
          onChangeText={(t) => onChange({ ...value, [k]: t })}
          keyboardType={KEYBOARD[k] ?? 'default'}
          autoCapitalize={k === 'email' || k === 'website' ? 'none' : 'sentences'}
          autoCorrect={false}
          multiline={k === 'memo' || k === 'address'}
        />
      ))}
    </>
  );
}
