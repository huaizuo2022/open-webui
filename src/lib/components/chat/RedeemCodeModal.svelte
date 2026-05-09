<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';

	const dispatch = createEventDispatcher();
	const i18n = getContext('i18n');

	export let show = false;
	export let loading = false;
	export let balance: number | null = null;
	export let freeChatUsed: number | null = null;
	export let freeChatLimit: number | null = null;

	let code = '';

	const submit = () => {
		dispatch('submit', { code: code.trim() });
	};

	$: if (!show) {
		code = '';
	}
</script>

<Modal bind:show size="sm">
	<div class="p-5">
		<div class="text-lg font-medium text-gray-900 dark:text-gray-100">
			{$i18n.t('Redeem Credits')}
		</div>

		<div class="mt-2 text-sm text-gray-500 dark:text-gray-400">
			{$i18n.t('Enter a redeem code to top up your balance for paid chat usage.')}
		</div>

		<div class="mt-4 rounded-2xl bg-gray-50 dark:bg-gray-850 px-4 py-3 text-sm">
			<div class="flex items-center justify-between gap-3">
				<span class="text-gray-500 dark:text-gray-400">{$i18n.t('Balance')}</span>
				<span class="font-semibold text-gray-900 dark:text-gray-100">{balance ?? 0}</span>
			</div>
			<div class="mt-2 flex items-center justify-between gap-3">
				<span class="text-gray-500 dark:text-gray-400">{$i18n.t('Free Chats')}</span>
				<span class="font-semibold text-gray-900 dark:text-gray-100">
					{freeChatUsed ?? 0} / {freeChatLimit ?? 0}
				</span>
			</div>
		</div>

		<div class="mt-4 flex flex-col gap-1.5">
			<label class="text-sm text-gray-600 dark:text-gray-300">{$i18n.t('Redeem Code')}</label>
			<input
				bind:value={code}
				class="rounded-2xl border border-gray-200 dark:border-gray-800 bg-transparent px-3 py-2 text-sm font-mono uppercase outline-hidden"
				placeholder="TB-XXXXXXXX"
				on:keydown={(event) => {
					if (event.key === 'Enter') {
						event.preventDefault();
						submit();
					}
				}}
			/>
		</div>

		<div class="mt-5 flex justify-end gap-2">
			<button
				type="button"
				class="px-4 py-2 rounded-2xl bg-gray-100 dark:bg-gray-800 text-sm"
				on:click={() => (show = false)}
			>
				{$i18n.t('Cancel')}
			</button>
			<button
				type="button"
				class="px-4 py-2 rounded-2xl bg-black text-white dark:bg-white dark:text-black text-sm disabled:opacity-60"
				disabled={loading || code.trim() === ''}
				on:click={submit}
			>
				{loading ? $i18n.t('Redeeming...') : $i18n.t('Redeem')}
			</button>
		</div>
	</div>
</Modal>
