<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Link from '$lib/components/icons/Link.svelte';
	import {
		completeFeishuAuth,
		getFeishuAuthStatus,
		pollFeishuAuth
	} from '$lib/apis/configs';

	const i18n = getContext('i18n');

	export let show = false;

	let loading = false;
	let starting = false;
	let status = null;
	let authPayload = null;
	let polling = false;
	let pollTimer = null;

	const loadStatus = async () => {
		loading = true;
		try {
			status = await getFeishuAuthStatus(localStorage.token);
		} catch (e) {
			console.error(e);
			toast.error($i18n.t('Failed to fetch Feishu authorization status'));
		} finally {
			loading = false;
		}
	};

	const startAuth = async () => {
		starting = true;
		try {
			authPayload = await completeFeishuAuth(localStorage.token);
			if (authPayload?.verification_url) {
				window.open(authPayload.verification_url, '_blank', 'noopener,noreferrer');
			}
			if (authPayload?.status === 'pending') {
				startPolling();
			} else {
				await loadStatus();
			}
		} catch (e) {
			console.error(e);
			toast.error($i18n.t('Failed to start Feishu authorization'));
		} finally {
			starting = false;
		}
	};

	const stopPolling = () => {
		polling = false;
		if (pollTimer) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	};

	const startPolling = () => {
		stopPolling();
		polling = true;
		pollTimer = setInterval(async () => {
			try {
				const result = await pollFeishuAuth(localStorage.token);
				if (result?.status === 'authorized') {
					stopPolling();
					authPayload = null;
					await loadStatus();
					toast.success($i18n.t('Feishu authorization completed'));
				} else if (result?.status === 'failed') {
					stopPolling();
					await loadStatus();
					toast.error(result?.error || $i18n.t('Feishu authorization failed'));
				} else if (result?.verification_url) {
					authPayload = result;
				}
			} catch (e) {
				console.error(e);
				stopPolling();
			}
		}, 3000);
	};

	$: if (show) {
		loadStatus();
	}

	$: if (!show) {
		stopPolling();
	}
</script>

<Modal bind:show size="sm">
	<div class="flex flex-col gap-4 p-5 text-sm text-gray-900 dark:text-gray-100">
		<div>
			<div class="text-base font-semibold">{$i18n.t('Authorize Feishu Search')}</div>
			<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
				{$i18n.t('Authorize lark-cli user access so chat can supplement answers with Feishu docs search.')}
			</div>
		</div>

		{#if loading}
			<div class="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
				<Spinner className="size-4" />
				<span>{$i18n.t('Checking authorization status...')}</span>
			</div>
		{:else if status}
			<div class="rounded-xl border border-gray-200 dark:border-gray-800 p-3">
				<div class="font-medium">
					{status.authorized ? $i18n.t('Authorized') : $i18n.t('Not Authorized')}
				</div>
				<div class="mt-2 text-xs text-gray-500 dark:text-gray-400">
					<div>identity: {status.identity || 'unknown'}</div>
					{#if status.user_name}
						<div>user: {status.user_name}</div>
					{/if}
					{#if status.note}
						<div class="mt-1 break-all">{status.note}</div>
					{/if}
				</div>
			</div>
		{/if}

		{#if !status?.authorized}
			<button
				class="flex items-center justify-center gap-2 rounded-xl bg-black text-white dark:bg-white dark:text-black px-4 py-2 text-sm disabled:opacity-60"
				on:click={startAuth}
				disabled={starting || polling}
			>
				{#if starting || polling}
					<Spinner className="size-4" />
				{:else}
					<Link />
				{/if}
				<span>{polling ? $i18n.t('Waiting for Authorization') : $i18n.t('Start Feishu Authorization')}</span>
			</button>
		{/if}

		{#if authPayload?.verification_url}
			<div class="rounded-xl border border-dashed border-gray-200 dark:border-gray-800 p-3 text-xs text-gray-500 dark:text-gray-400">
				<div class="font-medium text-gray-700 dark:text-gray-200">{$i18n.t('Authorization Link')}</div>
				<a
					class="mt-2 block break-all text-blue-600 dark:text-blue-400 hover:underline"
					href={authPayload.verification_url}
					target="_blank"
					rel="noopener noreferrer"
				>
					{authPayload.verification_url}
				</a>
				{#if authPayload.expires_in}
					<div class="mt-2">{$i18n.t('Expires in {{seconds}} seconds', { seconds: authPayload.expires_in })}</div>
				{/if}
			</div>
		{/if}

		<div class="flex justify-end">
			<button
				class="rounded-xl border border-gray-200 dark:border-gray-700 px-4 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800"
				on:click={() => (show = false)}
			>
				{$i18n.t('Close')}
			</button>
		</div>
	</div>
</Modal>
