<script lang="ts">
	import { createEventDispatcher, getContext, onMount } from 'svelte';
	import { goto } from '$app/navigation';

	import { toast } from 'svelte-sonner';

	import { getBackendConfig, getSessionUser, userSignIn, userSignUp } from '$lib/apis/auths';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import { config, user, socket } from '$lib/stores';

	import { generateInitialsImage, getUserTimezone } from '$lib/utils';
	import { updateUserTimezone } from '$lib/apis/users';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let show = false;

	let mode: 'signin' | 'signup' = 'signin';

	let name = '';
	let email = '';
	let password = '';
	let confirmPassword = '';

	let loading = false;

	$: enableSignup = $config?.features?.enable_signup ?? true;
	$: enableSignupPasswordConfirmation = $config?.features?.enable_signup_password_confirmation ?? false;

	const setSessionUser = async (sessionUser) => {
		if (sessionUser) {
			toast.success($i18n.t(`You're now logged in.`));
			if (sessionUser.token) {
				localStorage.token = sessionUser.token;
			}
			$socket.emit('user-join', { auth: { token: sessionUser.token } });
			await user.set(sessionUser);
			await config.set(await getBackendConfig());

			const timezone = getUserTimezone();
			if (sessionUser.token && timezone) {
				updateUserTimezone(sessionUser.token, timezone);
			}

			show = false;
			dispatch('success', sessionUser);
		}
	};

	const signInHandler = async () => {
		if (loading) return;
		loading = true;

		const sessionUser = await userSignIn(email, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		await setSessionUser(sessionUser);
		loading = false;
	};

	const signUpHandler = async () => {
		if (loading) return;
		loading = true;

		if (enableSignupPasswordConfirmation) {
			if (password !== confirmPassword) {
				toast.error($i18n.t('Passwords do not match.'));
				loading = false;
				return;
			}
		}

		const sessionUser = await userSignUp(name, email, password, generateInitialsImage(name)).catch(
			(error) => {
				toast.error(`${error}`);
				return null;
			}
		);

		await setSessionUser(sessionUser);
		loading = false;
	};

	const submitHandler = async () => {
		if (mode === 'signin') {
			await signInHandler();
		} else {
			await signUpHandler();
		}
	};

	const handleKeydown = (e: KeyboardEvent) => {
		if (e.key === 'Enter') {
			submitHandler();
		}
	};
</script>

{#if show}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
		on:click|self={() => {
			show = false;
		}}
	>
		<div
			class="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl dark:bg-gray-800"
			on:keydown={handleKeydown}
		>
			<div class="mb-6 text-center">
				<h2 class="text-2xl font-semibold text-gray-900 dark:text-white">
					{mode === 'signin' ? $i18n.t('Sign In') : $i18n.t('Sign Up')}
				</h2>
				<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
					{mode === 'signin'
						? $i18n.t('Welcome back! Please sign in to continue.')
						: $i18n.t('Create an account to get started.')}
				</p>
			</div>

			<form on:submit|preventDefault={submitHandler} class="space-y-4">
				{#if mode === 'signup'}
					<div>
						<label for="name" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
							{$i18n.t('Name')}
						</label>
						<input
							id="name"
							type="text"
							bind:value={name}
							required
							class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
							placeholder={$i18n.t('Enter your name')}
						/>
					</div>
				{/if}

				<div>
					<label for="email" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
						{$i18n.t('Email')}
					</label>
					<input
						id="email"
						type="email"
						bind:value={email}
						required
						class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
						placeholder={$i18n.t('Enter your email')}
					/>
				</div>

				<div>
					<label for="password" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
						{$i18n.t('Password')}
					</label>
					<SensitiveInput
						id="password"
						bind:value={password}
						required
						class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
						placeholder={$i18n.t('Enter your password')}
					/>
				</div>

				{#if mode === 'signup' && enableSignupPasswordConfirmation}
					<div>
						<label
							for="confirmPassword"
							class="block text-sm font-medium text-gray-700 dark:text-gray-300"
						>
							{$i18n.t('Confirm Password')}
						</label>
						<SensitiveInput
							id="confirmPassword"
							bind:value={confirmPassword}
							required
							class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
							placeholder={$i18n.t('Confirm your password')}
						/>
					</div>
				{/if}

				<button
					type="submit"
					disabled={loading}
					class="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
				>
					{#if loading}
						<div class="flex items-center justify-center gap-2">
							<Spinner className="size-4" />
							<span>{$i18n.t('Loading...')}</span>
						</div>
					{:else}
						{mode === 'signin' ? $i18n.t('Sign In') : $i18n.t('Sign Up')}
					{/if}
				</button>
			</form>

			<div class="mt-4 text-center text-sm">
				{#if mode === 'signin'}
					{#if enableSignup}
						<span class="text-gray-600 dark:text-gray-400">
							{$i18n.t("Don't have an account?")}
						</span>
						<button
							type="button"
							class="ml-1 text-blue-600 hover:text-blue-700 dark:text-blue-400"
							on:click={() => {
								mode = 'signup';
								name = '';
								password = '';
								confirmPassword = '';
							}}
						>
							{$i18n.t('Sign Up')}
						</button>
					{/if}
				{:else}
					<span class="text-gray-600 dark:text-gray-400">
						{$i18n.t('Already have an account?')}
					</span>
					<button
						type="button"
						class="ml-1 text-blue-600 hover:text-blue-700 dark:text-blue-400"
						on:click={() => {
							mode = 'signin';
							name = '';
							password = '';
							confirmPassword = '';
						}}
					>
						{$i18n.t('Sign In')}
					</button>
				{/if}
			</div>

			<button
				type="button"
				class="mt-4 w-full rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
				on:click={() => {
					show = false;
				}}
			>
				{$i18n.t('Cancel')}
			</button>
		</div>
	</div>
{/if}
