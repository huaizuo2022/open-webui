import { describe, expect, it } from 'vitest';

import { createOpenAITextStream, isOpenAITextStreamResponse } from './index';

function buildSseStream(events: string[]): ReadableStream<Uint8Array> {
	const encoder = new TextEncoder();
	return new ReadableStream<Uint8Array>({
		start(controller) {
			for (const event of events) {
				controller.enqueue(encoder.encode(`data: ${event}\n\n`));
			}
			controller.close();
		}
	});
}

describe('createOpenAITextStream', () => {
	it('emits assistant message content from non-stream completion payloads', async () => {
		const stream = buildSseStream([
			JSON.stringify({
				choices: [
					{
						message: {
							content: '高德券通常不支持实物商品'
						}
					}
				]
			}),
			'[DONE]'
		]);

		const iterator = await createOpenAITextStream(stream, false);
		const updates = [];
		for await (const update of iterator) {
			updates.push(update);
		}

		expect(updates[0]).toMatchObject({
			done: false,
			value: '',
			content: '高德券通常不支持实物商品'
		});
		expect(updates.at(-1)).toMatchObject({ done: true, value: '' });
	});

	it('emits full content snapshots from webui streaming events', async () => {
		const stream = buildSseStream([
			JSON.stringify({ content: '<details type="reasoning" done="false">\n<summary>Thinking…</summary>\nfoo\n</details>' }),
			'[DONE]'
		]);

		const iterator = await createOpenAITextStream(stream, false);
		const updates = [];
		for await (const update of iterator) {
			updates.push(update);
		}

		expect(updates[0]).toMatchObject({
			done: false,
			value: '',
			content: '<details type="reasoning" done="false">\n<summary>Thinking…</summary>\nfoo\n</details>'
		});
		expect(updates.at(-1)).toMatchObject({ done: true, value: '' });
	});

	it('emits chat id metadata from webui streaming events', async () => {
		const stream = buildSseStream([
			JSON.stringify({ chat_id: 'chat-123' }),
			'[DONE]'
		]);

		const iterator = await createOpenAITextStream(stream, false);
		const updates = [];
		for await (const update of iterator) {
			updates.push(update);
		}

		expect(updates[0]).toMatchObject({
			done: false,
			value: '',
			chatId: 'chat-123'
		});
		expect(updates.at(-1)).toMatchObject({ done: true, value: '' });
	});

	it('still emits delta content from openai-compatible chunk events', async () => {
		const stream = buildSseStream([
			JSON.stringify({ choices: [{ delta: { content: '你好' } }] }),
			'[DONE]'
		]);

		const iterator = await createOpenAITextStream(stream, false);
		const updates = [];
		for await (const update of iterator) {
			updates.push(update);
		}

		expect(updates[0]).toMatchObject({
			done: false,
			value: '你好'
		});
		expect(updates.at(-1)).toMatchObject({ done: true, value: '' });
	});

	it('converts reasoning deltas into visible content snapshots', async () => {
		const stream = buildSseStream([
			JSON.stringify({ choices: [{ delta: { reasoning_content: '先想一下' } }] }),
			JSON.stringify({ choices: [{ delta: { content: '最终答案' } }] }),
			'[DONE]'
		]);

		const iterator = await createOpenAITextStream(stream, false);
		const updates = [];
		for await (const update of iterator) {
			updates.push(update);
		}

		expect(updates[0]).toMatchObject({
			done: false,
			value: '',
			content: '<details type="reasoning" done="false">\n<summary>Thinking…</summary>\n> 先想一下\n</details>'
		});
		expect(updates[1]).toMatchObject({
			done: false,
			value: '',
			content:
				'<details type="reasoning" done="false">\n<summary>Thinking…</summary>\n> 先想一下\n</details>最终答案'
		});
		expect(updates.at(-1)).toMatchObject({ done: true, value: '' });
	});

	it('emits final content before closing when a stream event includes done and content', async () => {
		const stream = buildSseStream([
			JSON.stringify({ done: true, content: '高德券通常不支持实物商品' }),
		]);

		const iterator = await createOpenAITextStream(stream, false);
		const updates = [];
		for await (const update of iterator) {
			updates.push(update);
		}

		expect(updates[0]).toMatchObject({
			done: false,
			value: '',
			content: '高德券通常不支持实物商品'
		});
		expect(updates[1]).toMatchObject({ done: true, value: '' });
	});
});

describe('isOpenAITextStreamResponse', () => {
	it('only treats event-stream responses as text streams', () => {
		expect(
			isOpenAITextStreamResponse(new Response('{}', { headers: { 'content-type': 'application/json' } }))
		).toBe(false);
		expect(
			isOpenAITextStreamResponse(
				new Response('', { headers: { 'content-type': 'text/event-stream; charset=utf-8' } })
			)
		).toBe(true);
	});
});
