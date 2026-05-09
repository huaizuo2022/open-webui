<script lang="ts">
	import { getContext } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import type { RedeemCodeBatchCreateResponse } from '$lib/apis/credits';

	const i18n = getContext('i18n');

	export let show = false;
	export let result: RedeemCodeBatchCreateResponse | null = null;

	const copyAll = async () => {
		if (!result?.codes?.length) return;
		await navigator.clipboard.writeText(result.codes.map((item) => item.code).join('\n'));
	};
</script>

<Modal bind:show size="md">
	<div class="p-5">
		<div class="flex items-start justify-between gap-4">
			<div>
				<div class="text-lg font-medium text-gray-900 dark:text-gray-100">
					{$i18n.t('Generated Redeem Codes')}
				</div>
				{#if result?.batch}
					<div class="mt-1 text-sm text-gray-500 dark:text-gray-400">
						{result.batch.batch_name} · {result.batch.quantity} · {result.batch.credit_amount}
					</div>
				{/if}
			</div>

			<button
				class="rounded-2xl bg-black text-white dark:bg-white dark:text-black px-3 py-1.5 text-sm"
				type="button"
				on:click={copyAll}
			>
				{$i18n.t('Copy All')}
			</button>
		</div>

		<div class="mt-4 max-h-[50vh] overflow-y-auto rounded-2xl border border-gray-100 dark:border-gray-800">
			{#each result?.codes ?? [] as item}
				<div class="px-4 py-2 border-b last:border-b-0 border-gray-100 dark:border-gray-800 font-mono text-sm">
					{item.code}
				</div>
			{/each}
		</div>
	</div>
</Modal>
