<script lang="ts">
	import Prompts from './Prompts.svelte';
	import Skills from './Skills.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Keyframes from '$lib/components/icons/Keyframes.svelte';

	export let query = '';
	export let onSelect = (e) => {};
	export let insertTextHandler = (text) => {};
	export let command: (payload: { id: string; label: string }) => void;

	let filteredItems = [];
	let selectedIdx = 0;
	let activeSection = 'prompts';

	let promptsComponent: Prompts;
	let skillsItems: any[] = [];

	const i18n = { t: (s: string) => s };

	const getItems = async () => {
		const res = await fetch(`/api/v1/skills/?q=${encodeURIComponent(query)}`).catch(() => null);
		if (res?.ok) {
			const data = await res.json();
			skillsItems = data.items || [];
		}
	};

	$: if (query !== undefined) {
		filteredItems = [];
		selectedIdx = 0;
		activeSection = 'prompts';
		getItems();
	}

	export const selectUp = () => {
		if (activeSection === 'prompts') {
			promptsComponent?.selectUp?.();
		} else {
			selectedIdx = Math.max(0, selectedIdx - 1);
		}
	};

	export const selectDown = () => {
		if (activeSection === 'prompts') {
			promptsComponent?.selectDown?.();
		} else {
			selectedIdx = Math.min(selectedIdx + 1, skillsItems.length - 1);
		}
	};

	export const select = () => {
		if (activeSection === 'prompts') {
			promptsComponent?.select?.();
		} else {
			const skill = skillsItems[selectedIdx];
			if (skill) {
				onSelect({ type: 'skill', data: skill });
			}
		}
	};

	$: promptItems = filteredItems;
	$: allItems = [...(promptItems || []), ...(skillsItems || [])];
</script>

{#if allItems.length > 0}
	<div class="overflow-y-auto scrollbar-thin max-h-60">
		{#if (promptItems || []).length > 0}
			<div class="px-2 py-1 text-xs text-gray-500">Prompts</div>
			<Prompts
				bind:this={promptsComponent}
				{query}
				bind:filteredItems
				onSelect={(e) => {
					if (e.type === 'prompt') {
						insertTextHandler(e.data.content);
					}
				}}
			/>
		{/if}

		{#if (skillsItems || []).length > 0}
			<div class="border-t border-gray-200 dark:border-gray-800 my-1" />
			<div class="px-2 py-1 text-xs text-gray-500">Skills</div>
			{#each skillsItems as skill, skillIdx (skill.id)}
				<Tooltip content={skill.description || skill.name} placement="top-start">
					<button
						class="px-2.5 py-1.5 rounded-xl w-full text-left {skillIdx === selectedIdx
							? 'bg-gray-50 dark:bg-gray-800 selected-command-option-button'
							: ''}"
						type="button"
						on:click={() => {
							onSelect({ type: 'skill', data: skill });
						}}
						on:mousemove={() => {
							selectedIdx = skillIdx;
						}}
						data-selected={skillIdx === selectedIdx}
					>
						<div class="flex text-black dark:text-gray-100 line-clamp-1 items-center">
							<div class="flex items-center justify-center size-5 mr-2 shrink-0">
								<Keyframes className="size-4" />
							</div>
							<div class="truncate">
								{skill.name}
							</div>
							<div class="ml-2 text-xs text-gray-500 truncate">
								{skill.id}
							</div>
						</div>
					</button>
				</Tooltip>
			{/each}
		{/if}
	</div>
{/if}