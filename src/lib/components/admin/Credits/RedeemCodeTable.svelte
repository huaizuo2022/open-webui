<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	import dayjs from '$lib/dayjs';
	import type { RedeemCode } from '$lib/apis/credits';

	const dispatch = createEventDispatcher();
	const i18n = getContext('i18n');

	export let items: RedeemCode[] = [];
	export let loading = false;
	export let selectedBatchId = '';
	export let selectedStatus = '';
	export let backendUnavailable = false;

	const batches = Array.from(new Set(items.map((item) => item.batch_id).filter(Boolean)));
	const statuses = ['unused', 'used'];
</script>

<div class="rounded-3xl border border-gray-100/40 dark:border-gray-850/40 bg-white dark:bg-gray-900 px-4 py-4">
	<div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
		<div>
			<div class="text-lg font-medium text-gray-900 dark:text-gray-100">
				{$i18n.t('Redeem Codes')}
			</div>
			<div class="text-sm text-gray-500 dark:text-gray-400">
				{items.length} {$i18n.t('items')}
			</div>
		</div>

		<div class="flex flex-col md:flex-row gap-2">
			<select
				bind:value={selectedBatchId}
				class="rounded-2xl border border-gray-200 dark:border-gray-800 bg-transparent px-3 py-2 text-sm outline-hidden"
				on:change={() => dispatch('filter')}
			>
				<option value="">{ $i18n.t('All batches') }</option>
				{#each batches as batchId}
					<option value={batchId}>{batchId}</option>
				{/each}
			</select>

			<select
				bind:value={selectedStatus}
				class="rounded-2xl border border-gray-200 dark:border-gray-800 bg-transparent px-3 py-2 text-sm outline-hidden"
				on:change={() => dispatch('filter')}
			>
				<option value="">{ $i18n.t('All statuses') }</option>
				{#each statuses as status}
					<option value={status}>{status}</option>
				{/each}
			</select>
		</div>
	</div>

	{#if backendUnavailable}
		<div class="mt-4 text-sm text-amber-600 dark:text-amber-400">
			{$i18n.t('Backend credit admin routes are not mounted yet, so this table cannot load in this environment.')}
		</div>
	{:else if loading}
		<div class="mt-4 text-sm text-gray-500 dark:text-gray-400">
			{$i18n.t('Loading redeem codes...')}
		</div>
	{:else if items.length === 0}
		<div class="mt-4 text-sm text-gray-500 dark:text-gray-400">
			{$i18n.t('No redeem codes found')}
		</div>
	{:else}
		<div class="mt-4 overflow-x-auto">
			<table class="min-w-full text-sm">
				<thead>
					<tr class="text-left text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-800">
						<th class="py-2 pr-4">{$i18n.t('Code')}</th>
						<th class="py-2 pr-4">{$i18n.t('Batch')}</th>
						<th class="py-2 pr-4">{$i18n.t('Credits')}</th>
						<th class="py-2 pr-4">{$i18n.t('Status')}</th>
						<th class="py-2 pr-4">{$i18n.t('Used By')}</th>
						<th class="py-2">{$i18n.t('Created')}</th>
					</tr>
				</thead>
				<tbody>
					{#each items as item}
						<tr class="border-b border-gray-50 dark:border-gray-850/60">
							<td class="py-2 pr-4 font-mono">{item.code}</td>
							<td class="py-2 pr-4 font-mono text-xs">{item.batch_id}</td>
							<td class="py-2 pr-4">{item.credit_amount}</td>
							<td class="py-2 pr-4 capitalize">{item.status}</td>
							<td class="py-2 pr-4 font-mono text-xs">{item.used_by_user_id ?? '-'}</td>
							<td class="py-2">{dayjs.unix(item.created_at).format('YYYY-MM-DD HH:mm')}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
