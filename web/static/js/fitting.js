const token = document.getElementById('csrf-token').value;
const statusElement = document.getElementById('fitting-status');
const resultsElement = document.getElementById('fitting-results');

function element(tag, text, parent) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (parent) parent.appendChild(node);
    return node;
}

async function callAPI(path, method, payload) {
    const response = await fetch(path, {
        method, headers: {'Content-Type': 'application/json', 'X-CSRF-Token': token},
        body: payload === undefined ? undefined : JSON.stringify(payload)
    });
    const data = await response.json().catch(() => ({error: 'Unexpected server response.'}));
    if (!response.ok) throw new Error(data.error || 'Request failed.');
    return data;
}

function feedbackForm(card, club, profile) {
    const form = element('form', undefined, card);
    element('h3', 'Record measured results for this club', form);
    for (const [name, label, max] of [
        ['carry_yards', 'Average carry (yards)', 400],
        ['dispersion_yards', 'Lateral dispersion (yards)', 150],
        ['shot_count', 'Number of measured shots (at least 5)', 500]
    ]) {
        const field = element('label', label, form);
        const input = element('input', undefined, field);
        input.name = name; input.type = 'number'; input.required = true;
        input.min = name === 'shot_count' ? '5' : '0';
        input.max = String(max); input.step = name === 'shot_count' ? '1' : '0.1';
    }
    const consentLabel = element('label', undefined, form);
    const consent = element('input', undefined, consentLabel);
    consent.type = 'checkbox'; consent.required = true;
    consentLabel.appendChild(document.createTextNode(
        ' I consent to saving these measurements and my questionnaire for recommendation training until I withdraw them.'
    ));
    const submit = element('button', 'Save measured feedback', form);
    submit.type = 'submit'; submit.className = 'btn';
    form.addEventListener('submit', async event => {
        event.preventDefault(); submit.disabled = true;
        try {
            const fields = new FormData(form);
            await callAPI('/api/outcomes', 'POST', {
                golf_club_id: club.id, profile, consent: consent.checked,
                carry_yards: Number(fields.get('carry_yards')),
                dispersion_yards: Number(fields.get('dispersion_yards')),
                shot_count: Number(fields.get('shot_count')),
                measured_at: new Date().toISOString()
            });
            statusElement.textContent = 'Feedback saved. Thank you.';
            form.reset();
        } catch (error) { statusElement.textContent = error.message; }
        finally { submit.disabled = false; }
    });
}

document.getElementById('fitting-form').addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.target.querySelector('button[type=submit]');
    button.disabled = true;
    resultsElement.replaceChildren();
    statusElement.textContent = 'Finding options…';
    const profile = Object.fromEntries(new FormData(event.target));
    for (const field of ['handicap', 'swing_speed_mph', 'budget', 'loft_degrees']) {
        if (profile[field] === '') delete profile[field];
        else profile[field] = Number(profile[field]);
    }
    try {
        const data = await callAPI('/api/recommendations', 'POST', profile);
        statusElement.textContent = data.recommendations.length ? data.notice :
            'No verified, fresh, in-stock options match your constraints. Try another budget or ask a fitter.';
        for (const club of data.recommendations) {
            const card = element('article', undefined, resultsElement);
            card.className = 'fitting-card';
            element('h2', `${club.brand_name || ''} ${club.model_name || ''}`, card);
            element('p', `Price: $${Number(club.price).toFixed(2)} · Method: ${club.method}`, card);
            const specs = club.club || club;
            element('p', `Hand: ${specs.hand || 'unknown'} · Loft: ${specs.loft_degrees ?? 'unknown'} · Shaft flex: ${specs.shaft_flex || 'unknown'}`, card);
            element('p', `Source: ${club.source_name || specs.source_name || 'unknown'} · Price checked: ${specs.price_checked_at || 'unknown'}`, card);
            element('p', `Score: ${Number(club.score).toFixed(3)} · Reference: ${Number(club.baseline_value).toFixed(3)}`, card);
            element('p', 'Signed contributions describe score influence, not causal performance improvement.', card);
            const list = element('ul', undefined, card);
            for (const part of [...(club.contributions || [])].sort(
                (left, right) => Math.abs(right.contribution) - Math.abs(left.contribution)
            )) {
                element('li', `${part.feature}: ${part.contribution >= 0 ? '+' : ''}${Number(part.contribution).toFixed(3)}`, list);
            }
            element('p', `Uncertainty: ${JSON.stringify(club.uncertainty)}`, card);
            for (const warning of club.limitations || []) element('p', warning, card);
            feedbackForm(card, club, profile);
        }
    } catch (error) { statusElement.textContent = error.message; }
    finally { button.disabled = false; }
});

document.getElementById('withdraw-feedback').addEventListener('click', async event => {
    event.target.disabled = true;
    try {
        const data = await callAPI('/api/outcomes', 'DELETE');
        statusElement.textContent = `Deleted ${data.deleted} feedback record(s).`;
    } catch (error) { statusElement.textContent = error.message; }
    finally { event.target.disabled = false; }
});
