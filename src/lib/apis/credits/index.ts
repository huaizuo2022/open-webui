import { WEBUI_API_BASE_URL } from '$lib/constants';
import { getDeviceHeaders } from '$lib/apis/device';

export type CreditSession = {
	balance: number;
	free_chat_used: number;
	free_chat_limit: number;
};

export type CreditSummary = CreditSession & {
	total_recharged: number;
	total_consumed: number;
};

export type RedeemCode = {
	id: string;
	batch_id: string;
	code: string;
	credit_amount: number;
	status: string;
	used_by_user_id?: string | null;
	used_at?: number | null;
	created_at: number;
};

export type RedeemCodeBatch = {
	id: string;
	batch_name: string;
	credit_amount: number;
	quantity: number;
	created_by: string;
	created_at: number;
};

export type RedeemCodeListResponse = {
	items: RedeemCode[];
	total: number;
};

export type RedeemCodeBatchCreateResponse = {
	batch: RedeemCodeBatch;
	codes: RedeemCode[];
};

const parseError = (err: any) => err?.detail ?? err?.error?.message ?? 'Request failed';

const authedJsonFetch = async (url: string, token: string, init: RequestInit = {}) => {
	let error = null;

	const res = await fetch(url, {
		...init,
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`,
			...getDeviceHeaders(),
			...(init.headers ?? {})
		}
	})
		.then(async (response) => {
			if (!response.ok) throw await response.json();
			return response.json();
		})
		.catch((err) => {
			console.error(err);
			error = parseError(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getMyCreditSummary = async (token: string): Promise<CreditSummary> => {
	return authedJsonFetch(`${WEBUI_API_BASE_URL}/credits/me`, token, { method: 'GET' });
};

export const redeemCreditsCode = async (token: string, code: string): Promise<CreditSummary> => {
	return authedJsonFetch(`${WEBUI_API_BASE_URL}/credits/redeem`, token, {
		method: 'POST',
		body: JSON.stringify({ code: code.trim() })
	});
};

export const listRedeemCodes = async (
	token: string,
	params: { batchId?: string; status?: string } = {}
): Promise<RedeemCodeListResponse> => {
	const searchParams = new URLSearchParams();
	if (params.batchId) {
		searchParams.set('batch_id', params.batchId);
	}
	if (params.status) {
		searchParams.set('status', params.status);
	}

	return authedJsonFetch(
		`${WEBUI_API_BASE_URL}/admin/credits/redeem-codes${searchParams.toString() ? `?${searchParams.toString()}` : ''}`,
		token,
		{ method: 'GET' }
	);
};

export const createRedeemCodeBatch = async (
	token: string,
	body: { batch_name: string; credit_amount: number; quantity: number }
): Promise<RedeemCodeBatchCreateResponse> => {
	return authedJsonFetch(`${WEBUI_API_BASE_URL}/admin/credits/redeem-codes/batches`, token, {
		method: 'POST',
		body: JSON.stringify(body)
	});
};

export const exportRedeemCodeBatch = async (
	token: string,
	batchId: string
): Promise<RedeemCodeListResponse> => {
	return authedJsonFetch(
		`${WEBUI_API_BASE_URL}/admin/credits/redeem-codes/batches/${batchId}/export`,
		token,
		{ method: 'GET' }
	);
};
