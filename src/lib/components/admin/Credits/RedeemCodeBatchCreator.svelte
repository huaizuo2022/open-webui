<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';

	const dispatch = createEventDispatcher();
	const i18n = getContext('i18n');

	export let creating = false;

	let batch_name = '';
	let credit_amount = 10;
	let quantity = 10;

	const submit = () => {
		dispatch('submit', {
			batch_name: batch_name.trim(),
			credit_amount: Number(credit_amount),
			quantity: Number(quantity)
		});
	};
</script>

<div class="rounded-3xl border border-gray-100/40 dark:border-gray-850/40 bg-white dark:bg-gray-900 px-4 py-4">
	<div class="text-lg font-medium text-gray-900 dark:text-gray-100">
		{$i18n.t('Create Redeem Batch')}
	</div>

	<div class="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
		<div class="flex flex-col gap-1.5">
			<label class="text-sm text-gray-600 dark:text-gray-300">{$i18n.t('Batch Name')}</label>
			<input
				bind:value={batch_name}
				class="rounded-2xl border border-gray-200 dark:border-gray-800 bg-transparent px-3 py-2 text-sm outline-hidden"
				placeholder={$i18n.t('e.g. May promo')}
			/>
		</div>

		<div class="flex flex-col gap-1.5">
			<label class="text-sm text-gray-600 dark:text-gray-300">{$i18n.t('Credit Amount')}</label>
			<input
				bind:value={credit_amount}
				type="number"
				min="1"
				class="rounded-2xl border border-gray-200 dark:border-gray-800 bg-transparent px-3 py-2 text-sm outline-hidden"
			/>
		</div>

		<div class="flex flex-col gap-1.5">
			<label class="text-sm text-gray-600 dark:text-gray-300">{$i18n.t('Quantity')}</label>
			<input
				bind:value={quantity}
				type="number"
				min="1"
				class="rounded-2xl border border-gray-200 dark:border-gray-800 bg-transparent px-3 py-2 text-sm outline-hidden"
			/>
		</div>
	</div>

	<div class="mt-4 flex justify-end">
		<button
			class="px-4 py-2 rounded-2xl bg-black text-white dark:bg-white dark:text-black disabled:opacity-60"
			type="button"
			disabled={creating || batch_name.trim() === '' || Number(credit_amount) <= 0 || Number(quantity) <= 0}
			on:click={submit}
		>
			{creating ? $i18n.t('Creating...') : $i18n.t('Create Batch')}
		</button>
	</div>
</div>
