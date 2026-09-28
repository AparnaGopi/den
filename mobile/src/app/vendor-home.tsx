import * as ImagePicker from 'expo-image-picker';
import { useRouter } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, Image, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ChoiceChip, ErrorNotice, Loading, discoveryStyles } from '@/components/discovery-ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Colors, Fonts, Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth-context';
import { ApiError } from '@/lib/api';
import { fieldChoices, stepAnswers, visibleField, type VendorWizard, type WizardAnswer, type WizardField } from '@/lib/vendor-wizard';
import { requestError } from '@/types/events';

type Upload = { field: 'logo' | 'cover' | 'photos'; assets: ImagePicker.ImagePickerAsset[] };
const endpoint = '/vendor/onboarding/';

export default function VendorHomeScreen() {
  const router = useRouter();
  const { user, status, authenticatedRequest, logout } = useAuth();
  const [wizard, setWizard] = useState<VendorWizard | null>(null);
  const [answers, setAnswers] = useState<VendorWizard['answers']>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const current = useRef<VendorWizard | null>(null);
  const values = useRef<VendorWizard['answers']>({});
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scroll = useRef<ScrollView>(null);
  const mounted = useRef(true);
  const conflict = useRef(false);
  const saveOnLeave = useRef<() => void>(() => {});

  const load = useCallback(async () => {
    setError(null);
    try {
      const saved = await authenticatedRequest<VendorWizard>(endpoint);
      current.current = saved; values.current = saved.answers; conflict.current = false;
      setWizard(saved); setAnswers(saved.answers); setErrors({});
      setNotice('Saved progress restored.');
    } catch (cause) { setError(requestError(cause)); }
  }, [authenticatedRequest]);

  const latestLoad = useRef(load);
  latestLoad.current = load;
  useEffect(() => {
    if (status === 'authenticated' && user?.role === 'customer') router.replace('/home');
    if (status === 'unauthenticated') router.replace('/');
    if (status === 'authenticated' && user?.role === 'vendor') void latestLoad.current();
  }, [router, status, user?.id, user?.role]);
  useEffect(() => {
    mounted.current = true;
    const listener = AppState.addEventListener('change', (state) => { if (state !== 'active') saveOnLeave.current(); });
    return () => { mounted.current = false; listener.remove(); saveOnLeave.current(); };
  }, []);

  function enqueue(action: string, target?: number, upload?: Upload, photoId?: string) {
    const pending = queue.current.catch(() => {}).then(async () => {
      const saved = current.current;
      if (!saved || conflict.current) return false;
      const sentAnswers = stepAnswers(saved, values.current);
      const body = new FormData();
      body.append('step', String(saved.step)); body.append('revision', String(saved.revision));
      body.append('action', action); body.append('answers', JSON.stringify(sentAnswers));
      if (target) body.append('target', String(target));
      if (photoId) body.append('photo_id', photoId);
      if (mounted.current) setNotice('Saving progress…');
      try {
        if (upload) for (const asset of upload.assets) {
          if (Platform.OS === 'web') body.append(upload.field, asset.file ?? await (await fetch(asset.uri)).blob(), asset.fileName || 'image.jpg');
          else body.append(upload.field, { uri: asset.uri, name: asset.fileName || 'image.jpg', type: asset.mimeType || 'image/jpeg' } as unknown as Blob);
        }
        const result = await authenticatedRequest<VendorWizard>(endpoint, { method: 'POST', body });
        current.current = result;
        if (mounted.current) {
          setWizard(result); setError(null); setErrors({});
          setNotice(action === 'submit' ? 'Submitted for admin approval.' : 'Progress saved. You can leave and return.');
        }
        if (action !== 'save') {
          values.current = result.answers;
          if (mounted.current) { setAnswers(result.answers); scroll.current?.scrollTo({ y: 0, animated: true }); }
        }
        return true;
      } catch (cause) {
        if (cause instanceof ApiError && cause.status === 409) conflict.current = true;
        if (cause instanceof ApiError && cause.status === 400 && cause.data && typeof cause.data === 'object' && 'revision' in cause.data) {
          const result = cause.data as VendorWizard;
          current.current = result;
          if (action !== 'save') { values.current = result.answers; if (mounted.current) setAnswers(result.answers); }
          if (mounted.current) { setWizard(result); setErrors(result.errors || {}); scroll.current?.scrollTo({ y: 0, animated: true }); }
        }
        if (mounted.current) { setError(requestError(cause)); setNotice('Check the highlighted answers or retry saving.'); }
        return false;
      }
    });
    queue.current = pending;
    return pending;
  }

  saveOnLeave.current = () => {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; void enqueue('save'); }
  };

  function update(name: string, value: WizardAnswer) {
    const next = { ...values.current, [name]: value };
    if (name === 'vendor_type' && current.current) {
      const allowed = new Set(current.current.service_catalogue.filter((item) => item.saved || item.types.includes(String(value))).map((item) => item.value));
      next.specific_services = (next.specific_services as string[]).filter((id) => allowed.has(id));
      if (value === 'OTHER') next.other_enabled = true;
    }
    values.current = next; setAnswers(next); setNotice('Unsaved changes…');
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { timer.current = null; void enqueue('save'); }, 800);
  }

  async function navigate(action: string, target?: number) {
    if (busy) return;
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    setBusy(true);
    try { await enqueue(action, target); } finally { if (mounted.current) setBusy(false); }
  }

  async function chooseImages(field: Upload['field']) {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    setBusy(true); setError(null);
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'], allowsMultipleSelection: field === 'photos', selectionLimit: field === 'photos' ? 20 : 1, quality: 0.85,
      });
      if (!result.canceled) {
        for (const asset of result.assets) {
          if (asset.fileSize && asset.fileSize > 5 * 1024 * 1024) throw new Error('Choose images of 5 MB or smaller.');
          if (asset.mimeType && !['image/jpeg', 'image/png', 'image/webp'].includes(asset.mimeType)) throw new Error('Choose JPEG, PNG or WebP images.');
        }
        await enqueue('save', undefined, { field, assets: result.assets });
      } else await enqueue('save');
    } catch (cause) { setError(requestError(cause)); }
    finally { if (mounted.current) setBusy(false); }
  }

  async function removePhoto(id: string) {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    setBusy(true);
    try { await enqueue('remove_photo', undefined, undefined, id); }
    finally { if (mounted.current) setBusy(false); }
  }

  async function signOut() {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    setBusy(true);
    try { if (await enqueue('save')) { await logout(); router.replace('/'); } }
    finally { if (mounted.current) setBusy(false); }
  }

  function renderField(field: WizardField) {
    if (!wizard || !visibleField(field, answers)) return null;
    const value = answers[field.name];
    const label = field.name === 'price' ? ({ HOURLY: 'Price per hour (CAD)', PER_PERSON: 'Price per person (CAD)', PER_ITEM: 'Price per item (CAD)', STARTING_FROM: 'Starting price (CAD)' }[String(answers.pricing_type)] || 'Fixed price (CAD)') : field.label;
    const fieldError = errors[field.name]?.join(' ');
    if (field.kind === 'tags' || field.kind === 'choice') return <View key={field.name} style={local.field}>
      <Text style={local.label}>{label}{field.required ? ' *' : ''}</Text>
      <View style={discoveryStyles.chips}>{fieldChoices(field, wizard, answers).map((option) => <ChoiceChip key={option.value} label={option.label}
        selected={field.kind === 'tags' ? (value as string[] || []).includes(option.value) : value === option.value} disabled={busy}
        onPress={() => update(field.name, field.kind === 'tags' ? ((value as string[] || []).includes(option.value) ? (value as string[]).filter((id) => id !== option.value) : [...(value as string[] || []), option.value]) : option.value)} />)}</View>
      {!!fieldError && <Text accessibilityRole="alert" style={local.error}>{fieldError}</Text>}
    </View>;
    if (field.kind === 'boolean') return <ChoiceChip key={field.name} label={label} selected={!!value} disabled={busy || (field.name === 'other_enabled' && answers.vendor_type === 'OTHER')} onPress={() => update(field.name, !value)} />;
    return <Input key={field.name} label={`${label}${field.required ? ' *' : ''}`} accessibilityLabel={label} value={String(value ?? '')} editable={!busy}
      error={fieldError} multiline={field.kind === 'textarea'} maxLength={field.max_length || undefined}
      autoCapitalize={field.kind === 'email' || field.name.endsWith('_url') ? 'none' : 'sentences'}
      keyboardType={field.kind === 'email' ? 'email-address' : field.kind === 'number' ? 'decimal-pad' : field.name === 'phone' ? 'phone-pad' : 'default'}
      onChangeText={(text) => update(field.name, text)} />;
  }

  if (status !== 'authenticated' || user?.role !== 'vendor') return null;
  if (!wizard) return <SafeAreaView style={local.safe}>{error ? <ErrorNotice message={error} retry={() => void load()} /> : <Loading />}</SafeAreaView>;
  const section = wizard.sections[wizard.step - 1];
  return <SafeAreaView style={local.safe}><ScrollView ref={scroll} keyboardShouldPersistTaps="handled" contentContainerStyle={local.content}>
    <View style={discoveryStyles.row}><Text style={local.wordmark}>den.</Text><Button label="Save & log out" variant="secondary" disabled={busy} onPress={() => void signOut()} /></View>
    <Text style={discoveryStyles.eyebrow}>VENDOR STUDIO</Text><Text style={discoveryStyles.title}>Your business, one step at a time.</Text>
    <Text style={discoveryStyles.badge}>{wizard.approval_label}</Text><Text style={discoveryStyles.body}>Submissions are reviewed by an admin before appearing in discovery.</Text>
    {!!wizard.review_feedback && <Text style={discoveryStyles.body}>Admin feedback: {wizard.review_feedback}</Text>}
    <Text accessibilityLiveRegion="polite" style={discoveryStyles.body}>{notice}</Text>
    {error && <ErrorNotice message={error} retry={conflict.current ? () => void load() : undefined} />}
    <View accessibilityRole="progressbar" accessibilityValue={{ min: 1, max: 6, now: wizard.step, text: `Step ${wizard.step} of 6: ${section.title}` }}>
      <Text style={local.label}>Step {wizard.step} of 6: {section.title}</Text><View style={local.track}><View style={[local.progress, { width: `${wizard.step / 6 * 100}%` }]} /></View>
    </View>
    <View style={discoveryStyles.chips}>{wizard.sections.map((item) => <ChoiceChip key={item.number} label={`${item.number}. ${item.title}`} selected={item.number === wizard.step} disabled={busy} onPress={() => void navigate('goto', item.number)} />)}</View>
    <View style={discoveryStyles.card}>
      <Text style={discoveryStyles.title}>{section.title}</Text>
      {wizard.step === 1 && <><Button label="Choose company logo" variant="secondary" disabled={busy} onPress={() => void chooseImages('logo')} />{wizard.logo_url && <Image source={{ uri: wizard.logo_url }} accessibilityLabel="Company logo" style={local.image} />}</>}
      {wizard.step === 4 && !!wizard.pricing_listing_title && <Text style={discoveryStyles.body}>Pricing for {wizard.pricing_listing_title}. Your other listings are kept.</Text>}
      {section.fields.map(renderField)}
      {wizard.step === 2 && <Text style={discoveryStyles.body}>Choose up to four services. Use Other for additional services. Previously saved services remain available to keep or remove.</Text>}
      {wizard.step === 5 && <><Text style={discoveryStyles.body}>Photos are optional. JPEG, PNG or WebP, up to 5 MB each.</Text>
        <Button label="Choose cover photo" variant="secondary" disabled={busy} onPress={() => void chooseImages('cover')} />
        {wizard.cover_url && <Image source={{ uri: wizard.cover_url }} accessibilityLabel="Cover photo" style={local.image} />}
        <Button label="Add portfolio photos" variant="secondary" disabled={busy} onPress={() => void chooseImages('photos')} />
        {wizard.photos.map((photo) => <View key={photo.id}><Image source={{ uri: photo.url }} accessibilityLabel={photo.caption || 'Portfolio photo'} style={local.image} /><Text style={discoveryStyles.body}>{photo.caption}</Text><Button label="Remove photo" variant="secondary" disabled={busy} onPress={() => void removePhoto(photo.id)} /></View>)}
      </>}
      {wizard.step === 6 && <><Text style={discoveryStyles.body}>Check your answers before submitting.</Text>{wizard.review.map((item) => <View key={item.step} style={local.review}>
        <View style={discoveryStyles.row}><Text style={local.label}>{item.title}</Text><Button label={`Edit ${item.title}`} variant="secondary" disabled={busy} onPress={() => void navigate('goto', item.step)} /></View>
        {item.rows.map((row) => <View key={row.label}><Text style={local.label}>{row.label}</Text><Text style={discoveryStyles.body}>{row.value}</Text></View>)}
        {item.step === 1 && (wizard.logo_url ? <Image source={{ uri: wizard.logo_url }} accessibilityLabel="Company logo" style={local.image} /> : <Text>No logo added.</Text>)}
        {item.step === 5 && <>{wizard.cover_url && <Image source={{ uri: wizard.cover_url }} accessibilityLabel="Cover photo" style={local.image} />}{wizard.photos.length === 0 && <Text>No portfolio photos added.</Text>}{wizard.photos.map((photo) => <View key={photo.id}><Image source={{ uri: photo.url }} accessibilityLabel={photo.caption || 'Portfolio photo'} style={local.image} /><Text>{photo.caption}</Text></View>)}</>}
      </View>)}</>}
    </View>
    <View style={local.field}>{wizard.step > 1 && <Button label="Back" variant="secondary" disabled={busy} onPress={() => void navigate('back')} />}
      <Button label="Save progress" variant="secondary" disabled={busy} onPress={() => void navigate('save')} />
      <Button label={wizard.step < 6 ? 'Continue' : 'Submit for admin approval'} loading={busy} onPress={() => void navigate(wizard.step < 6 ? 'next' : 'submit')} />
    </View>
  </ScrollView></SafeAreaView>;
}

const local = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.light.background },
  content: { padding: Spacing.four, paddingBottom: Spacing.six, gap: Spacing.three, maxWidth: 800, width: '100%', alignSelf: 'center' },
  wordmark: { color: Colors.light.ink, fontFamily: Fonts.serif, fontSize: 34, fontWeight: '700' },
  image: { width: 150, height: 150, borderRadius: 16 },
  field: { gap: Spacing.two }, label: { color: Colors.light.ink, fontSize: 15, fontWeight: '600' }, error: { color: Colors.light.error },
  track: { height: 8, borderRadius: 4, backgroundColor: Colors.light.line, marginTop: 8 }, progress: { height: 8, borderRadius: 4, backgroundColor: Colors.light.terracotta },
  review: { gap: Spacing.two, paddingVertical: Spacing.three, borderBottomWidth: 1, borderBottomColor: Colors.light.line },
});
