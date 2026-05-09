const DEVICE_ID_STORAGE_KEY = 'owui_device_id';
export const DEVICE_ID_HEADER = 'X-OWUI-Device-Id';

const generateDeviceId = () => {
	if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
		return crypto.randomUUID();
	}

	return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
		const random = Math.floor(Math.random() * 16);
		const value = char === 'x' ? random : (random & 0x3) | 0x8;
		return value.toString(16);
	});
};

export const getDeviceId = () => {
	if (typeof localStorage === 'undefined') {
		return '';
	}

	let deviceId = localStorage.getItem(DEVICE_ID_STORAGE_KEY);
	if (!deviceId) {
		deviceId = generateDeviceId();
		localStorage.setItem(DEVICE_ID_STORAGE_KEY, deviceId);
	}

	return deviceId;
};

export const getDeviceHeaders = () => {
	const deviceId = getDeviceId();
	return deviceId ? { [DEVICE_ID_HEADER]: deviceId } : {};
};
