import * as ImagePicker from 'expo-image-picker';
import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Image, Linking, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ChoiceChip, ErrorNotice, Loading, discoveryStyles } from '@/components/discovery-ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Colors, Fonts, Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth-context';
import { requestError, type Category } from '@/types/events';

type VendorProfile = {
  id: number; business_name: string; category: number | null; phone: string; city: string; service_area: string;
  short_description: string; profile_image_url: string | null; approval_status: 'DRAFT' | 'PENDING' | 'APPROVED' | 'REJECTED';
  approval_label: string; full_profile_url: string;
};
type Form = Pick<VendorProfile, 'business_name' | 'category' | 'phone' | 'city' | 'service_area' | 'short_description'>;

export default function VendorHomeScreen() {
  const router = useRouter();
  const { user, status, authenticatedRequest, logout } = useAuth();
  const [profile, setProfile] = useState<VendorProfile | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [image, setImage] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [saved, choices] = await Promise.all([authenticatedRequest<VendorProfile>('/vendor/profile/'), authenticatedRequest<Category[]>('/categories/')]);
      setProfile(saved); setForm({ business_name: saved.business_name, category: saved.category, phone: saved.phone, city: saved.city, service_area: saved.service_area, short_description: saved.short_description }); setCategories(choices);
    } catch (cause) { setError(requestError(cause)); } finally { setLoading(false); }
  }, [authenticatedRequest]);
  useFocusEffect(useCallback(() => {
    if (status === 'authenticated' && user?.role === 'customer') router.replace('/home');
    if (status === 'authenticated' && user?.role === 'vendor') void load();
    if (status === 'unauthenticated') router.replace('/');
  }, [load, router, status, user?.role]));
  function update<K extends keyof Form>(key: K, value: Form[K]) { setForm((old) => old ? { ...old, [key]: value } : old); }
  async function chooseImage() {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) { setError('Photo-library permission is needed to choose a profile image.'); return; }
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, aspect: [1, 1], quality: 0.85 });
    if (!result.canceled) setImage(result.assets[0]);
  }
  async function save() {
    if (!form) return;
    setSaving(true); setError(null);
    try {
      const body = new FormData();
      body.append('business_name', form.business_name.trim()); body.append('phone', form.phone.trim()); body.append('city', form.city.trim());
      body.append('service_area', form.service_area.trim()); body.append('short_description', form.short_description.trim());
      if (form.category) body.append('category', String(form.category));
      if (image) body.append('profile_image', { uri: image.uri, name: image.fileName || 'profile.jpg', type: image.mimeType || 'image/jpeg' } as unknown as Blob);
      const saved = await authenticatedRequest<VendorProfile>('/vendor/profile/', { method: 'PATCH', body });
      setProfile(saved); setForm({ business_name: saved.business_name, category: saved.category, phone: saved.phone, city: saved.city, service_area: saved.service_area, short_description: saved.short_description }); setImage(null);
    } catch (cause) { setError(requestError(cause)); } finally { setSaving(false); }
  }
  async function signOut() { await logout(); router.replace('/'); }
  if (loading && !profile) return <SafeAreaView style={local.safe}><Loading /></SafeAreaView>;
  if (status !== 'authenticated' || user?.role !== 'vendor') return null;
  return <SafeAreaView style={local.safe}><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={local.content}>
    <View style={discoveryStyles.row}><Text style={local.wordmark}>den<Text style={local.dot}>.</Text></Text><Button label="Log out" variant="secondary" onPress={() => void signOut()} /></View>
    <Text style={discoveryStyles.eyebrow}>VENDOR STUDIO</Text><Text style={discoveryStyles.title}>Your business, at a glance.</Text>
    {profile && <View style={discoveryStyles.card}><Text style={discoveryStyles.badge}>{profile.approval_label.toUpperCase()}</Text><Text style={discoveryStyles.body}>{profile.approval_status === 'APPROVED' ? 'Your active profile can appear in customer discovery.' : profile.approval_status === 'REJECTED' ? 'Your profile needs changes before it can appear in discovery.' : 'Your profile will stay private until an admin approves it.'}</Text></View>}
    {error && <ErrorNotice message={error} retry={!profile ? () => void load() : undefined} />}
    {form && <View style={discoveryStyles.card}>
      {(image?.uri || profile?.profile_image_url) && <Image source={{ uri: image?.uri || profile?.profile_image_url || '' }} alt="Vendor profile preview" style={local.image} />}
      <Button label="Choose profile image" variant="secondary" disabled={saving} onPress={() => void chooseImage()} />
      <Input label="Business name" value={form.business_name} editable={!saving} maxLength={160} onChangeText={(value) => update('business_name', value)} />
      <Text style={discoveryStyles.body}>Primary category</Text><View style={discoveryStyles.chips}>{categories.map((category) => <ChoiceChip key={category.id} label={category.name} selected={form.category === category.id} disabled={saving} onPress={() => update('category', category.id)} />)}</View>
      <Input label="Phone" keyboardType="phone-pad" value={form.phone} editable={!saving} maxLength={30} onChangeText={(value) => update('phone', value)} />
      <Input label="City" value={form.city} editable={!saving} maxLength={100} onChangeText={(value) => update('city', value)} />
      <Input label="Service area" value={form.service_area} editable={!saving} maxLength={200} onChangeText={(value) => update('service_area', value)} />
      <Input label="Short description" value={form.short_description} editable={!saving} multiline maxLength={500} onChangeText={(value) => update('short_description', value)} />
      <Button label="Save basic information" loading={saving} onPress={() => void save()} />
    </View>}
    {profile && <Button label="Edit full profile on web" variant="secondary" onPress={() => { void Linking.openURL(profile.full_profile_url).catch((cause: unknown) => setError(requestError(cause))); }} />}
    <Text style={discoveryStyles.body}>Services, tasks, tags, prices, products, portfolio photos, availability and Google Business details are managed in the full web studio.</Text>
  </ScrollView></SafeAreaView>;
}
const local = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.light.background }, content: { padding: Spacing.four, paddingBottom: Spacing.six, gap: Spacing.three, maxWidth: 800, width: '100%', alignSelf: 'center' },
  wordmark: { color: Colors.light.ink, fontFamily: Fonts.serif, fontSize: 34, fontWeight: '700' }, dot: { color: Colors.light.terracotta }, image: { width: 104, height: 104, borderRadius: 24, alignSelf: 'center' },
});
