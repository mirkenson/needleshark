const RETRY = 'Не удалось выполнить проверку отправки. Данные остались в форме. Повторите попытку или напишите на sales@neesha.ru.';

// WebCrypto runs small batches asynchronously so the page remains responsive.
// This is a cost for automated submissions, not a claim that the visitor is human.
export async function solveProof(challenge, difficulty, {cryptoApi = globalThis.crypto, now = () => performance.now()} = {}) {
  if (typeof challenge !== 'string' || challenge.length > 200 || difficulty !== 14 || !cryptoApi?.subtle) throw new Error(RETRY);
  const encoder = new TextEncoder();
  const deadline = now() + 15000;
  for (let start = 0; start < 2 ** 24; start += 64) {
    if (now() > deadline) throw new Error(RETRY);
    const results = await Promise.all(Array.from({length: 64}, async (_, offset) => {
      const nonce = start + offset;
      const hash = new Uint8Array(await cryptoApi.subtle.digest('SHA-256', encoder.encode(`${challenge}:${nonce}`)));
      return hash[0] === 0 && hash[1] < 4 ? nonce : null;
    }));
    const nonce = results.find(value => value !== null);
    if (nonce !== undefined) return {challenge, nonce};
  }
  throw new Error(RETRY);
}

export async function browserProof(send, id) {
  const response = await send('/api/leads', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: 'challenge', id}), signal: AbortSignal.timeout(15000)
  });
  const result = await response.json().catch(() => null);
  if (response.status !== 200 || result?.ok !== true) {
    throw new Error(response.status === 429 ? 'Слишком много попыток. Попробуйте позже или напишите на sales@neesha.ru.' : RETRY);
  }
  return solveProof(result.challenge, result.difficulty);
}
