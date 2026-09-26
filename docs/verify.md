# Verify a certificate

Check a Monte-Neo `strategy-verdict/1` certificate in your browser. The check runs locally:
the certificate and the key are not sent anywhere.

A **valid signature** means the certificate was not edited after it was signed. Add the issuer's
public key to also check **who** signed it. A signature does not re-run the checks; to reproduce
the numbers, run `monte-neo verify --recheck` with the original data and strategy.

<form id="mn-verify-form" markdown="0">
  <p><label for="mn-cert-file"><strong>Certificate</strong> (JSON file, or paste it below)</label><br/>
  <input id="mn-cert-file" type="file" accept=".json,application/json"/></p>
  <p><textarea id="mn-cert" rows="10" style="width:100%;font-family:monospace;border:1px solid #8888;padding:4px" placeholder='{"schema": "strategy-verdict/1", ...}'></textarea></p>
  <p><label for="mn-key"><strong>Issuer's public key</strong> (optional)</label><br/>
  <input id="mn-key" type="text" style="width:100%;font-family:monospace;border:1px solid #8888;padding:4px" placeholder="ed25519:..."/></p>
  <p><button type="submit" class="md-button md-button--primary">Verify</button></p>
</form>

<div id="mn-verify-result" markdown="0"></div>

## Link straight to a check

Put the certificate somewhere public (for example, commit `verdict.json` to your repository) and
link to this page with two parameters:

```text
https://neozork.github.io/Monte-Neo/verify/?cert=<https URL of the certificate JSON>&key=ed25519:<your public key>
```

The page loads the certificate and checks it right away. Use this link behind the
"Verified by Monte-Neo" badge:

```markdown
[![Verified by Monte-Neo](https://img.shields.io/badge/verified%20by-Monte--Neo-2ea44f)](https://neozork.github.io/Monte-Neo/verify/?cert=https://raw.githubusercontent.com/OWNER/REPO/main/verdict.json&key=ed25519:KEY)
```

## Requirements and command-line alternative

Ed25519 in the browser needs a current Chrome, Edge, Firefox or Safari. The same check from the
command line:

```bash
pip install "monte-neo[sign]"
monte-neo verify --check-signature verdict.json --public-key issuer.pub
```

How signing works: [Verifier API → Signing a certificate](api/verify.md#signing-a-certificate).
