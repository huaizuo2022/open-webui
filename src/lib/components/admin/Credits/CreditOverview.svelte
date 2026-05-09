<script lang="ts">
	import { getContext } from 'svelte';
	import dayjs from '$lib/dayjs';
	import type { CreditSummary } from '$lib/apis/credits';

	const i18n = getContext('i18n');

	export let summary: CreditSummary | null = null;
	export let loading = false;
	export let error = '';
	export let isBackendUnavailable = false;

	const cards = (creditSummary: CreditSummary | null) => [
		{
			label: $i18n.t('Balance'),
			value: creditSummary?.balance ?? 0
		},
		{
			label: $i18n.t('Total Recharged'),
			value: creditSummary?.total_recharged ?? 0
		},
		{
			label: $i18n.t('Total Consumed'),
			value: creditSummary?.total_consumed ?? 0
		},
		{
			label: $i18n.t('Free Chats Used'),
			value: `${creditSummary?.free_chat_used ?? 0} / ${creditSummary?.free_chat_limit ?? 0}`
		}
	];
</script>

<div class="flex flex-col gap-4">
	<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
		{#each cards(summary) as card}
			<div class="rounded-3xl border border-gray-100/40 dark:border-gray-850/40 bg-white dark:bg-gray-900 px-4 py-4">
				<div class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
					{card.label}
				</div>
				<div class="mt-2 text-2xl font-semibold text-gray-900 dark:text-gray-50">
					{card.value}
				</div>
			</div>
		{/each}
	</div>

	<div class="rounded-3xl border border-gray-100/40 dark:border-gray-850/40 bg-white dark:bg-gray-900 px-4 py-4 text-sm text-gray-600 dark:text-gray-300">
		{#if loading}
			{$i18n.t('Loading credit summary...')}
		{:else if isBackendUnavailable}
			{$i18n.t('Credits frontend is ready, but backend credit routes are not mounted in this environment yet.')}
		{:else if error}
			{error}
		{:else}
			{$i18n.t('This view reads the current admin session credit summary and free-chat quota counters from the credits API.')}
		{/if}

		{#if summary}
			<div class="mt-3 text-xs text-gray-500 dark:text-gray-400">
				{$i18n.t('Updated')} {dayjs().format('YYYY-MM-DD HH:mm:ss')}
			</div>
		{/if}
	</div>
</div>
