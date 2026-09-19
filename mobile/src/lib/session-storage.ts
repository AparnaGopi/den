import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const isWeb = Platform.OS === 'web';

// The web fallback is for local development only. Production web should use secure HTTP-only cookies.
function getWebStorage(): Storage | null {
  if (!isWeb || typeof window === 'undefined') return null;
  return window.localStorage;
}

export async function getItem(key: string): Promise<string | null> {
  const storage = getWebStorage();
  if (storage) return storage.getItem(key);
  return SecureStore.getItemAsync(key);
}

export async function setItem(key: string, value: string): Promise<void> {
  const storage = getWebStorage();
  if (storage) {
    storage.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

export async function deleteItem(key: string): Promise<void> {
  const storage = getWebStorage();
  if (storage) {
    storage.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}
