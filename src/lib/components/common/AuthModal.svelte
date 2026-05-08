<script lang="ts">
	import { createEventDispatcher, getContext, onMount } from 'svelte';
	import { goto } from '$app/navigation';

	import { toast } from 'svelte-sonner';

	import { getBackendConfig, getSessionUser, userSignIn, userSignUp, sendVerificationCode, signInWithCode } from '$lib/apis/auths';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import { config, user, socket } from '$lib/stores';

	import { generateInitialsImage, getUserTimezone } from '$lib/utils';
	import { updateUserTimezone } from '$lib/apis/users';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let show = false;

	let mode: 'signin' | 'signup' | 'verification' = 'signin';

	let name = '';
	let email = '';
	let password = '';
	let confirmPassword = '';
	let verificationCode = '';

	let loading = false;
	let sendingCode = false;
	let countdown = 0;
	let countdownInterval: any;

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

	const sendCodeHandler = async () => {
		if (sendingCode || countdown > 0) return;
		if (!email) {
			toast.error($i18n.t('Please enter your email address.'));
			return;
		}

		sendingCode = true;
		const result = await sendVerificationCode(email).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (result) {
			toast.success($i18n.t('Verification code sent to your email.'));
			// Start countdown
			countdown = 60;
			countdownInterval = setInterval(() => {
				countdown--;
				if (countdown <= 0) {
					clearInterval(countdownInterval);
				}
			}, 1000);
		}
		sendingCode = false;
	};

	const signInWithCodeHandler = async () => {
		if (loading) return;
		if (!verificationCode) {
			toast.error($i18n.t('Please enter the verification code.'));
			return;
		}

		loading = true;

		const sessionUser = await signInWithCode(email, verificationCode).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		await setSessionUser(sessionUser);
		loading = false;
	};

	const submitHandler = async () => {
		if (mode === 'signin') {
			await signInHandler();
		} else if (mode === 'signup') {
			await signUpHandler();
		} else if (mode === 'verification') {
			await signInWithCodeHandler();
		}
	};

	const switchMode = (newMode: 'signin' | 'signup' | 'verification') => {
		mode = newMode;
		name = '';
		password = '';
		confirmPassword = '';
		verificationCode = '';
		if (countdownInterval) {
			clearInterval(countdownInterval);
			countdown = 0;
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
					{#if mode === 'signin'}
						{$i18n.t('Sign In')}
					{:else if mode === 'signup'}
						{$i18n.t('Sign Up')}
					{:else}
						{$i18n.t('Verification Code Login')}
					{/if}
				</h2>
				<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
					{#if mode === 'signin'}
						{$i18n.t('Welcome back! Please sign in to continue.')}
					{:else if mode === 'signup'}
						{$i18n.t('Create an account to get started.')}
					{:else}
						{$i18n.t('Enter the verification code sent to your email.')}
					{/if}
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

				{#if mode === 'verification'}
					<div>
						<label for="verificationCode" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
							{$i18n.t('Verification Code')}
						</label>
						<div class="mt-1 flex gap-2">
							<input
								id="verificationCode"
								type="text"
								bind:value={verificationCode}
								required
								maxlength="6"
								class="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
								placeholder={$i18n.t('Enter 6-digit code')}
							/>
							<button
								type="button"
								disabled={sendingCode || countdown > 0}
								on:click={sendCodeHandler}
								class="whitespace-nowrap rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-blue-600 transition hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:text-blue-400 dark:hover:bg-gray-700"
							>
								{#if sendingCode}
									<div class="flex items-center gap-1">
										<Spinner className="size-3" />
										<span>{$i18n.t('Sending...')}</span>
									</div>
								{:else if countdown > 0}
									{countdown}s
								{:else}
									{$i18n.t('Send Code')}
								{/if}
							</button>
						</div>
					</div>
				{:else}
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
					{:else if mode === 'verification'}
						{$i18n.t('Sign In')}
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
							on:click={() => switchMode('signup')}
						>
							{$i18n.t('Sign Up')}
						</button>
					{/if}
					<span class="mx-2 text-gray-400">|</span>
					<button
						type="button"
						class="text-blue-600 hover:text-blue-700 dark:text-blue-400"
						on:click={() => switchMode('verification')}
					>
						{$i18n.t('Verification Code Login')}
					</button>
				{:else if mode === 'signup'}
					<span class="text-gray-600 dark:text-gray-400">
						{$i18n.t('Already have an account?')}
					</span>
					<button
						type="button"
						class="ml-1 text-blue-600 hover:text-blue-700 dark:text-blue-400"
						on:click={() => switchMode('signin')}
					>
						{$i18n.t('Sign In')}
					</button>
				{:else}
					<span class="text-gray-600 dark:text-gray-400">
						{$i18n.t('Back to')}
					</span>
					<button
						type="button"
						class="ml-1 text-blue-600 hover:text-blue-700 dark:text-blue-400"
						on:click={() => switchMode('signin')}
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
