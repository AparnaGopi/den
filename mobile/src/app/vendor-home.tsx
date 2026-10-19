import * as ImagePicker from 'expo-image-picker';
import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Image, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ChoiceChip, ErrorNotice, Loading, discoveryStyles as s } from '@/components/discovery-ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/context/auth-context';
import { requestError } from '@/types/events';
import type { ChatPlan, QuickProfile, VisitStats } from '@/types/chat';

export default function VendorHomeScreen() {
  const router = useRouter();
  const { user, status, authenticatedRequest, logout } = useAuth();
  const [profile, setProfile] = useState<QuickProfile | null>(null);
  const [stats, setStats] = useState<VisitStats | null>(null);
  const [plan, setPlan] = useState<ChatPlan | null>(null);
  const [logo, setLogo] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [pictures, setPictures] = useState<ImagePicker.ImagePickerAsset[]>([]);
  const [areasOpen, setAreasOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const load = useCallback(async () => {
    try { setProfile(await authenticatedRequest<QuickProfile>('/vendor/quick-profile/')); setError(null); }
    catch (cause) { setError(requestError(cause)); }
  }, [authenticatedRequest]);
  useEffect(() => {
    if (status === 'unauthenticated') router.replace('/');
    if (status === 'authenticated' && user?.role !== 'vendor') router.replace('/home');
  }, [router, status, user?.role]);
  useFocusEffect(useCallback(() => {
    if (status === 'authenticated' && user?.role === 'vendor') {
      void authenticatedRequest<VisitStats>('/vendor/visit-stats/').then(setStats).catch(() => {});
      void authenticatedRequest<ChatPlan>('/vendor/chat-plan/').then(setPlan).catch(() => {});
    }
  }, [authenticatedRequest, status, user?.role]));
  useEffect(() => { if (status === 'authenticated' && user?.role === 'vendor') void load(); }, [load, status, user?.role]);
  function update<K extends keyof QuickProfile>(key: K, value: QuickProfile[K]) { setProfile((current) => current ? { ...current, [key]: value } : current); }
  async function choose(kind: 'logo' | 'pictures') {
    setError(null);
    try {
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsMultipleSelection: kind === 'pictures', selectionLimit: kind === 'pictures' ? 20 : 1, quality: 0.85 });
      if (result.canceled) return;
      for (const asset of result.assets) if (asset.fileSize && asset.fileSize > 5 * 1024 * 1024) throw new Error('Choose photos of 5 MB or smaller.');
      if (kind === 'logo') setLogo(result.assets[0]); else setPictures(result.assets);
    } catch (cause) { setError(requestError(cause)); }
  }
  async function save(submit: boolean) {
    if (!profile || busy) return;
    setBusy(true); setError(null); setNotice('');
    try {
      const body = new FormData();
      for (const key of ['business_name', 'short_description', 'city', 'other_services'] as const) body.append(key, profile[key]);
      profile.help_types.forEach((value) => body.append('help_types', value));
      profile.service_locations.forEach((value) => body.append('service_locations', String(value)));
      if (submit) body.append('submit', '1');
      async function append(field: string, asset: ImagePicker.ImagePickerAsset) {
        if (Platform.OS === 'web') body.append(field, asset.file ?? await (await fetch(asset.uri)).blob(), asset.fileName || 'image.jpg');
        else body.append(field, { uri: asset.uri, name: asset.fileName || 'image.jpg', type: asset.mimeType || 'image/jpeg' } as unknown as Blob);
      }
      if (logo) await append('profile_image', logo);
      for (const picture of pictures) await append('pictures', picture);
      setProfile(await authenticatedRequest<QuickProfile>('/vendor/quick-profile/', { method: 'POST', body }));
      setLogo(null); setPictures([]); setNotice(submit ? 'Saved and submitted for admin approval.' : 'Company details and photos saved.');
    } catch (cause) { setError(requestError(cause)); } finally { setBusy(false); }
  }
  async function removePhoto(id: number) {
    if (busy) return; setBusy(true); setError(null);
    try { await authenticatedRequest(`/vendor/portfolio/${id}/`, { method: 'DELETE' }); update('photos', profile!.photos.filter((photo) => photo.id !== id)); }
    catch (cause) { setError(requestError(cause)); } finally { setBusy(false); }
  }
  if (status === 'loading') return <Loading />;
  if (status !== 'authenticated' || user?.role !== 'vendor') return null;
  return <SafeAreaView style={s.safeArea}><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={s.content}>
    <Text style={s.title}>Your company, simply.</Text>
    <Button label="Client messages" variant="secondary" onPress={() => router.push('/messages')} />
    {stats && <Text style={s.body}>{stats.total_views} profile visits · {stats.unique_customers} unique customers · {stats.last_7_days} visits this week</Text>}
    {plan && <Button label={plan.active ? 'Chat subscription active' : `${plan.free_clients_remaining} free client chats left`} variant="secondary" onPress={() => router.push('/chat-plan')} />}
    {error && <ErrorNotice message={error} retry={!profile ? () => void load() : undefined} />}
    {!profile && !error && <Loading />}
    {profile && <>
      <Text style={s.badge}>{profile.approval_status}</Text>
      {!!profile.review_feedback && <Text style={s.body}>{profile.review_feedback}</Text>}
      <Input label="Company name" value={profile.business_name} editable={!busy} onChangeText={(text) => update('business_name', text)} maxLength={160} />
      <Button label="Choose logo (optional)" variant="secondary" disabled={busy} onPress={() => void choose('logo')} />
      {(logo?.uri || profile.logo_url) && <Image source={{ uri: logo?.uri || profile.logo_url! }} accessibilityLabel="Company logo" style={{ width: 110, height: 110, borderRadius: 12 }} />}
      <Input label="Short description" value={profile.short_description} multiline maxLength={500} editable={!busy} onChangeText={(text) => update('short_description', text)} />
      <Text style={s.heading}>Things you do</Text><Text style={s.body}>Choose the service tags customers use in their search.</Text>
      <View style={s.chips}>{profile.help_choices.map((choice) => <ChoiceChip key={choice.value} label={choice.label} selected={profile.help_types.includes(choice.value)} disabled={busy} onPress={() => update('help_types', profile.help_types.includes(choice.value) ? profile.help_types.filter((value) => value !== choice.value) : [...profile.help_types, choice.value])} />)}</View>
      {profile.help_types.includes('OTHER') && <Input label="Other services — please specify" value={profile.other_services} multiline editable={!busy} onChangeText={(text) => update('other_services', text)} />}
      <Input label="Your city in the GTA" value={profile.city} editable={!busy} onChangeText={(text) => update('city', text)} />
      <Button label={areasOpen ? 'Hide other service areas' : 'Other areas you serve (optional)'} variant="secondary" disabled={busy} onPress={() => setAreasOpen(!areasOpen)} />
      {areasOpen && <View style={s.chips}>{profile.location_choices.map((area) => <ChoiceChip key={area.id} label={area.name} selected={profile.service_locations.includes(area.id)} disabled={busy} onPress={() => update('service_locations', profile.service_locations.includes(area.id) ? profile.service_locations.filter((id) => id !== area.id) : [...profile.service_locations, area.id])} />)}</View>}
      <Text style={s.heading}>Pictures of your work</Text><Button label="Add pictures" variant="secondary" disabled={busy} onPress={() => void choose('pictures')} />
      {pictures.length > 0 && <><Text style={s.body}>{pictures.length} photos ready to upload when you save.</Text><View style={s.chips}>{pictures.map((asset) => <Image key={asset.uri} source={{ uri: asset.uri }} accessibilityLabel="Photo ready to upload" style={{ width: 90, height: 90, borderRadius: 10 }} />)}</View><Button label="Clear selected photos" variant="secondary" disabled={busy} onPress={() => setPictures([])} /></>}
      <View style={s.chips}>{profile.photos.map((photo) => <View key={photo.id} style={{ gap: 8 }}><Image source={{ uri: photo.url }} accessibilityLabel="Your work" style={{ width: 120, height: 120, borderRadius: 10 }} /><Button label="Remove photo" variant="secondary" disabled={busy} onPress={() => void removePhoto(photo.id)} /></View>)}</View>
      {!!notice && <Text accessibilityRole="alert" style={s.body}>{notice}</Text>}
      <Button label="Save details" loading={busy} onPress={() => void save(false)} />
      {profile.approval_status !== 'APPROVED' && <Button label="Save & submit for approval" variant="secondary" disabled={busy} onPress={() => void save(true)} />}
      <Button label="More details with guided setup" variant="secondary" disabled={busy} onPress={() => router.push('/vendor-guided')} />
    </>}
    <Button label="Log out" variant="secondary" disabled={busy} onPress={() => { void logout().then(() => router.replace('/')); }} />
  </ScrollView></SafeAreaView>;
}
