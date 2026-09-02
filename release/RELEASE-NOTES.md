# Gaffer 1.0.0 — macOS

**Gaffer-1.0.0-macOS.zip** · 14.2 MB
`sha256 a87c3656e6f4e2096e125431cecba77d928396a3aa3f1276049690416894672b`

Self-contained. Python and every dependency are inside the bundle — nothing to
install first.

## Installing

1. Unzip and drag **Gaffer.app** to Applications.
2. **First launch: right-click the app and choose Open**, then click Open again.

macOS blocks apps from unidentified developers on a normal double-click. Gaffer
is ad-hoc signed, not notarised — notarising needs a $99/yr Apple Developer
account. The right-click step is only needed once.

## First run

Enter your FPL team ID and you're in. No account required.

Your ID is the number in the URL of your Points page:
`fantasy.premierleague.com/entry/<YOUR ID>/history`

## Where it puts things

`~/Library/Application Support/Gaffer/` — config, cache and logs. The app
itself stays read-only. Delete that folder to reset it completely.

## What it does not do

It never asks for your FPL password, cannot sign in to your account, and cannot
change your team. Everything it reads is public data. Every recommendation ends
with you typing it into FPL yourself.

Requires macOS 11 or later.
