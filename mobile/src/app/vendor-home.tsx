import * as ImagePicker from 'expo-image-picker';
import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Image, Linking, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ChoiceChip, ErrorNotice, Loading, discoveryStyles } from '@/components/discovery-ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Colors, Fonts, Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth-context';
import { requestError, type Category } from '@/types/events';

type VendorProfile = {
  id: number; business_name: string; category: number | null; additional_categories: number[]; phone: string; city: string; service_area: string;
  short_description: string; profile_image_url: string | null; approval_status: 'DRAFT' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'CHANGES_REQUESTED';
  approval_label: string; full_profile_url: string; review_feedback: string;
  contact_first_name: string; contact_last_name: string; business_email: string; website_url: string; instagram_url: string; google_business_url: string; service_tags: number[]; service_locations: number[];
};
type Form = Pick<VendorProfile, 'business_name' | 'category' | 'additional_categories' | 'phone' | 'city' | 'service_area' | 'short_description' | 'contact_first_name' | 'contact_last_name' | 'business_email' | 'website_url' | 'instagram_url' | 'google_business_url' | 'service_tags' | 'service_locations'>;
type Option = { id: number; name: string };
type Portfolio = { id: number; image: string; caption: string };
const contactFields = ['contact_first_name', 'contact_last_name', 'business_email', 'website_url', 'instagram_url', 'google_business_url'] as const;
const contactLabels = ['Contact first name', 'Contact last name', 'Business email', 'Website URL', 'Instagram URL', 'Google Business URL'];

export default function VendorHomeScreen() {
  const router = useRouter();
  const { user, status, authenticatedRequest, logout } = useAuth();
  const [profile, setProfile] = useState<VendorProfile | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [showAllVendorCategories, setShowAllVendorCategories] = useState(false);
  const [image, setImage] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [options, setOptions] = useState<{ service_tags: Option[]; locations: Option[] }>({ service_tags: [], locations: [] });
  const [portfolio, setPortfolio] = useState<Portfolio[]>([]);
  const [portfolioImage, setPortfolioImage] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [caption, setCaption] = useState('');
  const [removeLogo, setRemoveLogo] = useState(false);
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [saved, choices, choicesExtra, photos] = await Promise.all([authenticatedRequest<VendorProfile>('/vendor/profile/'), authenticatedRequest<Category[]>('/categories/'), authenticatedRequest<{ service_tags: Option[]; locations: Option[] }>('/vendor/options/'), authenticatedRequest<Portfolio[]>('/vendor/portfolio/')]);
      setOptions(choicesExtra); setPortfolio(photos);
      setProfile(saved); setForm(saved); setCategories(choices);
    } catch (cause) { setError(requestError(cause)); } finally { setLoading(false); }
  }, [authenticatedRequest]);
  useFocusEffect(useCallback(() => {
    if (status === 'authenticated' && user?.role === 'customer') router.replace('/home');
    if (status === 'authenticated' && user?.role === 'vendor') void load();
    if (status === 'unauthenticated') router.replace('/');
  }, [load, router, status, user?.role]));
  function update<K extends keyof Form>(key: K, value: Form[K]) { setForm((old) => old ? { ...old, [key]: value } : old); }
  const vendorFeaturedCategories = categories.filter((category) => category.is_featured || form?.additional_categories.includes(category.id));
  const vendorExtraCategories = categories.filter((category) => !vendorFeaturedCategories.includes(category));
  const visibleVendorCategories = showAllVendorCategories ? categories : vendorFeaturedCategories;
  async function chooseImage(forPortfolio = false) {
    setError(null);
    try {
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, aspect: [1, 1], quality: 0.85 });
      if (!result.canceled) {
        const selected = result.assets[0];
        if (selected.fileSize && selected.fileSize > 5 * 1024 * 1024) throw new Error('Choose an image smaller than 5 MB.');
        if (selected.mimeType && !['image/jpeg', 'image/png', 'image/webp'].includes(selected.mimeType)) throw new Error('Choose a JPEG, PNG or WebP image.');
        if (forPortfolio) setPortfolioImage(selected); else { setImage(selected); setRemoveLogo(false); }
      }
    } catch (cause) { setError(requestError(cause)); }
  }
  async function save() {
    if (!form) return;
    setSaving(true); setError(null);
    try {
      const body = new FormData();
      Object.entries(form).forEach(([key, value]) => {
        if (['id', 'approval_status', 'approval_label', 'full_profile_url', 'profile_image_url', 'review_feedback'].includes(key)) return;
        if (Array.isArray(value)) { value.forEach((id) => body.append(key, String(id))); }
        else if (value !== null) body.append(key, String(value));
      });
      // Explicit flags distinguish an empty multi-select from an omitted PATCH field.
      if (!form.service_tags.length) body.append('clear_service_tags', 'true');
      if (!form.service_locations.length) body.append('clear_service_locations', 'true');
      if (!form.additional_categories.length) body.append('clear_additional_categories', 'true');
      body.append('remove_logo', String(removeLogo));
      if (image) await appendImage(body, 'profile_image', image);
      const saved = await authenticatedRequest<VendorProfile>('/vendor/profile/', { method: 'PATCH', body });
      setNotice('Profile saved. Use the full web editor to preview and submit for approval.'); setRemoveLogo(false);
      setProfile(saved); setForm(saved); setImage(null);
    } catch (cause) { setError(requestError(cause)); } finally { setSaving(false); }
  }
  async function appendImage(body: FormData, field: string, asset: ImagePicker.ImagePickerAsset) {
    if (Platform.OS === 'web') body.append(field, asset.file ?? await (await fetch(asset.uri)).blob(), asset.fileName || 'image.jpg');
    else body.append(field, { uri: asset.uri, name: asset.fileName || 'image.jpg', type: asset.mimeType || 'image/jpeg' } as unknown as Blob);
  }
  async function uploadPortfolio() {
    if (!portfolioImage) return;
    setSaving(true); setError(null);
    try {
      const body = new FormData(); await appendImage(body, 'image', portfolioImage); body.append('caption', caption);
      const saved = await authenticatedRequest<Portfolio>('/vendor/portfolio/', { method: 'POST', body });
      setPortfolio((old) => [saved, ...old]); setPortfolioImage(null); setCaption(''); setNotice('Portfolio image uploaded.');
    } catch (cause) { setError(requestError(cause)); } finally { setSaving(false); }
  }
  async function deletePortfolio(id: number) {
    setSaving(true); setError(null);
    try { await authenticatedRequest(`/vendor/portfolio/${id}/`, { method: 'DELETE' }); setPortfolio((old) => old.filter((photo) => photo.id !== id)); }
    catch (cause) { setError(requestError(cause)); } finally { setSaving(false); }
  }
  async function signOut() { await logout(); router.replace('/'); }
  if (loading && !profile) return <SafeAreaView style={local.safe}><Loading /></SafeAreaView>;
  if (status !== 'authenticated' || user?.role !== 'vendor') return null;
  return <SafeAreaView style={local.safe}><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={local.content}>
    <View style={discoveryStyles.row}><Text style={local.wordmark}>den<Text style={local.dot}>.</Text></Text><Button label="Log out" variant="secondary" onPress={() => void signOut()} /></View>
    <Text style={discoveryStyles.eyebrow}>VENDOR STUDIO</Text><Text style={discoveryStyles.title}>Your business, at a glance.</Text>
    {profile && <View style={discoveryStyles.card}><Text style={discoveryStyles.badge}>{profile.approval_label.toUpperCase()}</Text><Text style={discoveryStyles.body}>{profile.approval_status === 'APPROVED' ? 'Your active profile can appear in customer discovery.' : profile.approval_status === 'REJECTED' ? 'Your profile needs changes before it can appear in discovery.' : 'Your profile will stay private until an admin approves it.'}</Text></View>}
    {!!notice && <Text accessibilityRole="alert" style={discoveryStyles.body}>{notice}</Text>}
    {!!profile?.review_feedback && <Text style={discoveryStyles.body}>Admin feedback: {profile.review_feedback}</Text>}
    {error && <ErrorNotice message={error} retry={!profile ? () => void load() : undefined} />}
    {form && <View style={discoveryStyles.card}>
      {!removeLogo && (image?.uri || profile?.profile_image_url) && <Image source={{ uri: image?.uri || profile?.profile_image_url || '' }} alt="Vendor profile preview" style={local.image} />}
      <Button label="Choose company logo" variant="secondary" disabled={saving} onPress={() => void chooseImage()} />
      {image && <Button label="Cancel selected logo" variant="secondary" disabled={saving} onPress={() => setImage(null)} />}
      {!!profile?.profile_image_url && <Button label={removeLogo ? 'Keep saved logo' : 'Remove saved logo on save'} variant="secondary" disabled={saving} onPress={() => { setRemoveLogo(!removeLogo); setImage(null); }} />}
      <Input label="Company name" value={form.business_name} editable={!saving} maxLength={160} onChangeText={(value) => update('business_name', value)} />
      <Text style={discoveryStyles.body}>Primary category</Text><View style={discoveryStyles.chips}>{categories.map((category) => <ChoiceChip key={category.id} label={category.name} selected={form.category === category.id} disabled={saving} onPress={() => update('category', category.id)} />)}</View>
      <Text style={discoveryStyles.body}>Additional service categories (up to three)</Text><View style={discoveryStyles.chips}>{visibleVendorCategories.map((category) => <ChoiceChip key={category.id} label={category.name} selected={form.additional_categories.includes(category.id)} disabled={saving || (!form.additional_categories.includes(category.id) && form.additional_categories.length >= 3)} onPress={() => update('additional_categories', form.additional_categories.includes(category.id) ? form.additional_categories.filter((id) => id !== category.id) : [...form.additional_categories, category.id])} />)}</View>
      {vendorExtraCategories.length > 0 && <Button label={showAllVendorCategories ? 'Show featured services' : 'Browse all services'} variant="secondary" disabled={saving} onPress={() => setShowAllVendorCategories(!showAllVendorCategories)} />}
      {contactFields.map((key, index) => <Input key={key} label={contactLabels[index]} value={form[key]} editable={!saving} autoCapitalize={index < 2 ? 'words' : 'none'} keyboardType={key === 'business_email' ? 'email-address' : 'default'} maxLength={index < 2 ? 150 : 200} onChangeText={(value) => update(key, value)} />)}
      <Text style={discoveryStyles.body}>Services</Text><View style={discoveryStyles.chips}>{options.service_tags.map((tag) => <ChoiceChip key={tag.id} label={tag.name} selected={form.service_tags.includes(tag.id)} disabled={saving} onPress={() => update('service_tags', form.service_tags.includes(tag.id) ? form.service_tags.filter((id) => id !== tag.id) : [...form.service_tags, tag.id])} />)}</View>
      <Text style={discoveryStyles.body}>Service areas</Text><View style={discoveryStyles.chips}>{options.locations.map((area) => <ChoiceChip key={area.id} label={area.name} selected={form.service_locations.includes(area.id)} disabled={saving} onPress={() => update('service_locations', form.service_locations.includes(area.id) ? form.service_locations.filter((id) => id !== area.id) : [...form.service_locations, area.id])} />)}</View>
      <Input label="Phone" keyboardType="phone-pad" value={form.phone} editable={!saving} maxLength={30} onChangeText={(value) => update('phone', value)} />
      <Input label="City" value={form.city} editable={!saving} maxLength={100} onChangeText={(value) => update('city', value)} />
      <View style={discoveryStyles.chips}>{options.locations.filter((area) => form.city.length > 0 && area.name.toLowerCase().includes(form.city.toLowerCase())).slice(0, 5).map((area) => <ChoiceChip key={area.id} label={area.name} selected={form.city === area.name} disabled={saving} onPress={() => update('city', area.name)} />)}</View>
      <Input label="Other service areas" value={form.service_area} editable={!saving} maxLength={200} onChangeText={(value) => update('service_area', value)} />
      <Input label="Short description" value={form.short_description} editable={!saving} multiline maxLength={500} onChangeText={(value) => update('short_description', value)} />
      <Button label="Save basic information" loading={saving} onPress={() => void save()} />
    </View>}
    {profile && <View style={discoveryStyles.card}>
      <Text style={discoveryStyles.title}>Portfolio</Text>
      <Button label="Choose portfolio image" disabled={saving} variant="secondary" onPress={() => void chooseImage(true)} />
      {portfolioImage && <><Image source={{ uri: portfolioImage.uri }} style={local.image} alt="New portfolio preview" /><Input label="Caption" value={caption} maxLength={240} editable={!saving} onChangeText={setCaption} /><Button label="Remove selected image" disabled={saving} variant="secondary" onPress={() => setPortfolioImage(null)} /><Button label="Upload portfolio image" loading={saving} onPress={() => void uploadPortfolio()} /></>}
      {portfolio.map((photo) => <View key={photo.id}><Image source={{ uri: photo.image }} style={local.image} alt={photo.caption || 'Portfolio image'} /><Text style={discoveryStyles.body}>{photo.caption}</Text><Button label="Delete portfolio image" disabled={saving} variant="secondary" onPress={() => void deletePortfolio(photo.id)} /></View>)}
    </View>}
    {profile && <Button label="Edit full profile on web" variant="secondary" onPress={() => { void Linking.openURL(profile.full_profile_url).catch((cause: unknown) => setError(requestError(cause))); }} />}
    <Text style={discoveryStyles.body}>Preview and submit your profile, add services and products, and manage advanced details in the full web studio.</Text>
  </ScrollView></SafeAreaView>;
}
const local = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.light.background }, content: { padding: Spacing.four, paddingBottom: Spacing.six, gap: Spacing.three, maxWidth: 800, width: '100%', alignSelf: 'center' },
  wordmark: { color: Colors.light.ink, fontFamily: Fonts.serif, fontSize: 34, fontWeight: '700' }, dot: { color: Colors.light.terracotta }, image: { width: 104, height: 104, borderRadius: 24, alignSelf: 'center' },
});
