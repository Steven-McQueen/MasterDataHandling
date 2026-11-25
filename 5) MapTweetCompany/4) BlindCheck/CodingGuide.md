# Coding guide for the blind check (Step 5.3.2)

This guide is fixed before coding starts. It restates the rules the LLM was given (`../1) LabelTweets/LLM_Prompt.md`, version 6) for a human reader, so that the coder and the LLM answer the same question. Where the guide and the prompt differ, the prompt decides.

## The task

Each row of the workbook is one post. Read it and answer two questions:

1. Which listed companies does the post refer to?
2. For each of them, what is the stance of the post toward that company?

You see the post, its date and its account. You do not see the LLM's answer, and you must not look it up. You may search for a company to find its listed parent.

## When a post refers to a company

A post refers to a company in one of three ways.

| Way | Meaning | Example |
|---|---|---|
| By name | The company's name, its ticker or its own account appears | "Nvidia", "$TSLA", "Fox News", "@nvidia" |
| By brand | A product, brand, service or subsidiary that belongs to one listed company | "iPhone" is Apple, "Instagram" is Meta Platforms, "CNN" is Warner Bros. Discovery |
| By executive | A named person, mentioned in connection with the company or their role in it, when the company itself is not named | "Tim Cook announced new U.S. plants" is Apple |

Write the listed parent, not the brand: Alphabet for Google or YouTube, Meta Platforms for Instagram, Fox Corporation for Fox News. A ticker is also accepted. One entry per company per post, however many times it is named.

Special cases, taken from the prompt:

- **Elon Musk.** "Elon", "Musk" or "@elonmusk" always counts as a reference to Tesla, whatever the topic. If the post concerns him in another role (DOGE, politics, X, SpaceX) and says nothing about Tesla, the stance is neutral. The stance follows the post only when it concerns Tesla itself.
- **Other executives in another capacity** (a CEO quoted on politics unrelated to the firm) are not a reference.
- **Journalists, anchors and hosts** are not executives. A post about a host alone has no reference. If the network is named ("ABC's Jimmy Kimmel"), the reference is the network's parent. A post that mocks the person (voice, looks, intelligence, ratings) is neutral toward the network. The stance follows the post only when it targets the network itself ("Fake News CNN", calls to boycott it or take its licence).
- **Truth Social, Truth+ and $DJT** are Trump Media & Technology Group. Trump Accounts, the Trump Gold Card and other government programmes are not a reference.
- **Mar-a-Lago, Trump Tower and Trump golf courses** are The Trump Organization (not listed). Public places named after Trump are not a reference.
- **"X"** is a company only when it clearly means the platform.
- **GE** alone is GE Aerospace. U.S. Kellogg cereals are WK Kellogg Co.
- **Companies that split.** Write the company that owns the brand on the date of the post: NBC and MSNBC are Comcast until the spin-off and Versant after it, and Tylenol is Kenvue, not Johnson & Johnson.

## What is not a reference

- Industries, commodities and groups of companies without a name ("Big Pharma", "the banks", "oil prices", "steel tariffs"). The LLM records these as indirect references, and the analysis does not use them. Do not write them down.
- Countries, governments, agencies and their accounts, parties, universities, sports teams, NGOs, and people acting as politicians.
- Policy themes and slogans ("Energy Dominance", "Made in the USA"), macro figures and markets (GDP, inflation, the Dow, the S&P 500).

Private and unlisted companies (Cargill, Koch Industries, the Washington Post) may be written down or left out. The scoring ignores them either way, because only companies in the trade universe count.

## Stance

The stance is that of the post toward that company, not the mood of the post.

| Stance | Meaning |
|---|---|
| positive | Praise, endorsement, celebrated good news, or the company doing something the author approves of (investing in America, moving production to the U.S., cutting prices, hiring) |
| neutral | A factual mention, a name in a list of attendees, a neutral citation, a passing mention without a judgment |
| negative | Criticism, a demand, an attack, blame, a threat, "fake news" |

The LLM gives a score from -1 to 1, and the analysis counts 0.5 or more as Praised and -0.5 or less as Roasted. Positive here corresponds to Praised and negative to Roasted, so mild approval and mild criticism count.

## Procedure

1. The sample, this guide and the scripts are committed before coding starts.
2. Each coder fills in their workbook alone, saves it under `coded/` as `BlindSample_A_coded.xlsx` or `BlindSample_B_coded.xlsx`, and commits it before opening the other coder's file.
3. `python ScoreBlind.py agreement` compares the two coders on the 100 shared posts and writes `coded/BlindDisagreements.xlsx`. It shows no LLM label.
4. The coders go through the disagreements together and fill in the joint answer. The file is saved as `coded/BlindResolved.xlsx` and committed.
5. `python ScoreBlind.py final` compares the LLM with the human answer. Nothing is recoded after this step.
