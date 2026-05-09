<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { page } from '$app/stores';

	import {
		createRedeemCodeBatch,
		exportRedeemCodeBatch,
		getMyCreditSummary,
		listRedeemCodes,
		type CreditSummary,
		type RedeemCodeBatchCreateResponse,
		type RedeemCodeListResponse
	} from '$lib/apis/credits';
	import {
		CreditOverview,
		RedeemCodeBatchCreator,
		RedeemCodeTable,
		GeneratedCodesModal
	} from '$lib/components/admin/Credits';

	const i18n = getContext('i18n');

	let selectedTab = 'overview';
	let loadingSummary = false;
	let loadingCodes = false;
	let creatingBatch = false;
	let backendUnavailable = false;
	let error = '';

	let summary: CreditSummary | null = null;
	let codes: RedeemCodeListResponse['items'] = [];
	let batchResult: RedeemCodeBatchCreateResponse | null = null;
	let showGeneratedCodes = false;
	let selectedBatchId = '';
	let selectedStatus = '';

	$: {
		const pathParts = $page.url.pathname.split('/');
		const tabFromPath = pathParts[pathParts.length - 1];
		selectedTab = ['overview', 'redeem-codes'].includes(tabFromPath) ? tabFromPath : 'overview';
	}

	const isBackendNotMountedError = (value: unknown) => {
		const message = String(value ?? '');
		return message.includes('Not Found') || message.includes('404');
	};

	const loadSummary = async () => {
		loadingSummary = true;
		error = '';
		try {
			summary = await getMyCreditSummary(localStorage.token);
		} catch (err) {
			error = String(err ?? '');
			if (isBackendNotMountedError(err)) {
				backendUnavailable = true;
			}
		} finally {
			loadingSummary = false;
		}
	};

	const loadCodes = async () => {
		loadingCodes = true;
		error = '';
		try {
			const response = await listRedeemCodes(localStorage.token, {
				batchId: selectedBatchId || undefined,
				status: selectedStatus || undefined
			});
			codes = response.items;
		} catch (err) {
			error = String(err ?? '');
			if (isBackendNotMountedError(err)) {
				backendUnavailable = true;
			}
		} finally {
			loadingCodes = false;
		}
	};

	const createBatch = async (event) => {
		creatingBatch = true;
		try {
			batchResult = await createRedeemCodeBatch(localStorage.token, event.detail);
			showGeneratedCodes = true;
			await loadCodes();
			toast.success($i18n.t('Redeem code batch created'));
		} catch (err) {
			toast.error(String(err ?? ''));
			if (isBackendNotMountedError(err)) {
				backendUnavailable = true;
			}
		} finally {
			creatingBatch = false;
		}
	};

	const exportBatch = async () => {
		if (!selectedBatchId) {
			toast.error($i18n.t('Select a batch first'));
			return;
		}

		try {
			const response = await exportRedeemCodeBatch(localStorage.token, selectedBatchId);
			const content = response.items.map((item) => item.code).join('\n');
			await navigator.clipboard.writeText(content);
			toast.success($i18n.t('Copied redeem codes to clipboard'));
		} catch (err) {
			toast.error(String(err ?? ''));
		}
	};

	onMount(async () => {
		await loadSummary();
		if (selectedTab === 'redeem-codes') {
			await loadCodes();
		}
	});

	$: if (selectedTab === 'redeem-codes') {
		loadCodes();
	}
</script>

<GeneratedCodesModal bind:show={showGeneratedCodes} result={batchResult} />

<div class="flex flex-col lg:flex-row w-full h-full pb-2 lg:space-x-4">
	<div
		class="mx-[16px] lg:mx-0 lg:px-[16px] flex flex-row overflow-x-auto gap-2.5 max-w-full lg:gap-1 lg:flex-col lg:flex-none lg:w-50 dark:text-gray-200 text-sm font-medium text-left scrollbar-none"
	>
		<a
			href="/admin/credits/overview"
			draggable="false"
			class="px-0.5 py-1 min-w-fit rounded-lg lg:flex-none flex text-right transition select-none {selectedTab ===
			'overview'
				? ''
				: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
		>
			<div class="self-center">{$i18n.t('Overview')}</div>
		</a>

		<a
			href="/admin/credits/redeem-codes"
			draggable="false"
			class="px-0.5 py-1 min-w-fit rounded-lg lg:flex-none flex text-right transition select-none {selectedTab ===
			'redeem-codes'
				? ''
				: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
		>
			<div class="self-center">{$i18n.t('Redeem Codes')}</div>
		</a>
	</div>

	<div class="flex-1 mt-1 lg:mt-0 px-[16px] lg:pr-[16px] lg:pl-0 overflow-y-auto">
		{#if selectedTab === 'overview'}
			<CreditOverview
				{summary}
				loading={loadingSummary}
				{error}
				isBackendUnavailable={backendUnavailable}
			/>
		{:else if selectedTab === 'redeem-codes'}
			<div class="flex flex-col gap-4">
				<RedeemCodeBatchCreator creating={creatingBatch} on:submit={createBatch} />

				<div class="flex justify-end">
					<button
						type="button"
						class="px-4 py-2 rounded-2xl bg-gray-100 dark:bg-gray-800 text-sm disabled:opacity-60"
						disabled={!selectedBatchId}
						on:click={exportBatch}
					>
						{$i18n.t('Copy Selected Batch Codes')}
					</button>
				</div>

				<RedeemCodeTable
					items={codes}
					loading={loadingCodes}
					bind:selectedBatchId
					bind:selectedStatus
					backendUnavailable={backendUnavailable}
					on:filter={loadCodes}
				/>
			</div>
		{/if}
	</div>
</div>
