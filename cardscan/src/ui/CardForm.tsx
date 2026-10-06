import { CardFields, FIELD_LABEL } from '../core/types';
import { Field } from './components';
import { t } from '../i18n';

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
          label={t(FIELD_LABEL[k])}
          value={value[k]}
          onChangeText={(ct) => onChange({ ...value, [k]: ct })}
          keyboardType={KEYBOARD[k] ?? 'default'}
          autoCapitalize={k === 'email' || k === 'website' ? 'none' : 'sentences'}
          autoCorrect={false}
          multiline={k === 'memo' || k === 'address'}
        />
      ))}
    </>
  );
}
