# Data

## data/raw (not committed)

`faers*.json`: raw openFDA `drug/event` responses. Recreate with `make fetch`. Query used: `receivedate:[20240101 TO 20241231] AND serious:1`, 300 records.

## data/mock_meddra.json

Every `reactionmeddrapt` value seen in the raw sample. MedDRA itself is licensed, so this is the dictionary. `dayzero.coding` adds lay-language synonyms.

## data/mock_rsi.json

Synthetic reference safety information. For each product with at least four reports, the commonest half of its reported terms is marked "expected". This is not the approved label. The file says so.

## data/samples

`inbox.json`: the synthetic inbox. Each message has `id`, `received_at`, `channel`, `sender`, `subject`, `body`. Receive times are rebased to the 30 days before generation so deadlines are live.

`answer_key.json`: keyed by message id.

```
{
  "MSG-0003": {
    "extraction": { ...dayzero.schema.Extraction... },
    "truth_case": "<FAERS safetyreportid>",
    "variant": "complete | no_reporter | no_patient | followup | duplicate",
    "duplicate_of": "MSG-0001 or null",
    "followup_of": "MSG-0002 or null"
  }
}
```

Variants: about 10% of root messages omit the reporter, 8% omit the patient. Each of those gets a follow-up two days later that supplies the missing fact, so day zero should move to the follow-up date. About 12% of complete cases get a second message from a different reporter type, with the age off by one and lay wording for the reactions.

What FAERS gives us: age, sex, suspect products, reactions as MedDRA preferred terms, seriousness flags, outcomes, reporter qualification, an event date for about half of records.

What we invent: names, initials, contact details, message wording, channel, receive time. Invented values are the answer key.
