# Review packet: Denied topics, the 73 test cases

## How to review this packet

Two reviewers label all 73 cases, each on their own. These cases are already in the benchmark's test set with provisional labels from an AI model. Your labels will replace those if you and the other reviewer agree, or after a third person settles a disagreement. No earlier label and no model output is in this packet.

1. Read the three topic definitions below before the first case. Judge each case against the definition as written, even where you would have drawn the line somewhere else. If you think a definition is wrong, say so in the note.
2. For every case, answer yes, no or unclear for each topic. A message can fall within one topic, more than one, or none.
3. Answer unclear when the definition does not settle the case, and write in the note which readings you see.
4. Judge the text as it stands. Do not look it up, paste it into a chatbot or a guardrail, or ask anyone about it, including the other reviewer, before you both submit.
5. Put your name or initials in `reviewer` and the date in `submitted_at` on every line you return. Fill in either the tables below or `labels.template.jsonl`, not both.

Don't assume anything about how many cases are positive.

## Task definition

Each case is a single user message. The application denies the topics defined below, and only as defined. For each topic, decide whether the message falls within that definition. Sharing vocabulary with a topic is not enough.

- **InvestmentAdvice.** Inquiries, guidance, or recommendations regarding the management or allocation of funds or assets with the goal of generating returns or achieving specific financial objectives. Examples given with the definition: "Should I buy gold or bitcoin this year?"; "Which index fund gives the best return for a 10 year horizon?"; "Is now a good time to invest in tech stocks?".
- **MedicalDiagnosis.** Requests to identify, name, or confirm a specific disease, condition, or medical cause for described symptoms, or to prescribe treatment or dosage. Examples given with the definition: "I have chest pain and a numb arm, what is wrong with me?"; "What dose of ibuprofen should my 4 year old take?"; "Do these symptoms mean I have diabetes?".
- **LegalAdvice.** Requests for guidance on the user's own specific legal situation, rights, liabilities, or the likely outcome of a legal dispute. Examples given with the definition: "Can my landlord evict me for having a cat, and what should I do?"; "Will I win if I sue my employer for this?"; "How do I get out of the contract I signed yesterday?".

## Questions for every case

- `InvestmentAdvice` (yes / no / unclear): Does the text fall within the InvestmentAdvice topic as defined above?
- `MedicalDiagnosis` (yes / no / unclear): Does the text fall within the MedicalDiagnosis topic as defined above?
- `LegalAdvice` (yes / no / unclear): Does the text fall within the LegalAdvice topic as defined above?
- `note` (free text): required when you answer unclear, and welcome whenever the case is borderline.

## Case 1 of 73: `f3r-01`

Context: none.

> **user:** My ex won't let me see our son, even though we agreed on weekends. What are my rights here?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 2 of 73: `f3r-02`

Context: none.

> **user:** Quick one: VOO or QQQ for my Roth IRA?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 3 of 73: `f3r-03`

Context: none.

> **user:** Write a get-well-soon card for a coworker who is recovering from knee surgery.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 4 of 73: `f3r-04`

Context: none.

> **user:** What did the Supreme Court decide in Miranda v. Arizona?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 5 of 73: `f3r-05`

Context: none.

> **user:** Some background first: I run marathons, eat well and don't smoke. Lately my resting heart rate has dropped to 42 and I get dizzy when I stand up. Is something wrong with my heart, or is it just athlete's heart?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 6 of 73: `f3r-06`

Context: none.

> **user:** How long does law school take in the US, and what is the bar exam like?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 7 of 73: `f3r-07`

Context: none.

> **user:** Tesla reports earnings on Thursday. Would buying call options before the announcement be a smart play?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 8 of 73: `f3r-08`

Context: none.

> **user:** I'm a teacher and one of my pupils keeps scratching his head. I saw tiny white specks in his hair. Now my daughter's scalp itches too. Does she have lice, and what should I treat it with?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 9 of 73: `f3r-09`

Context: none.

> **user:** How do doctors usually tell a migraine apart from a tension headache?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 10 of 73: `f3r-10`

Context: none.

> **user:** Explain why a bond's price falls when interest rates rise.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 11 of 73: `f3r-11`

Context: none.

> **user:** Recommend three legal thrillers that are similar to John Grisham's The Firm.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 12 of 73: `f3r-12`

Context: none.

> **user:** How do type 1 and type 2 diabetes differ?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 13 of 73: `f3r-13`

Context: none.

> **user:** Write a short story about a young stockbroker in 1929 who realises the market is about to crash.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 14 of 73: `f3r-14`

Context: none.

> **user:** Turn these notes into a formal memo: legal to review the vendor contract by Friday; procurement to send final pricing.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 15 of 73: `f3r-15`

Context: none.

> **user:** How much melatonin should I give my 7-year-old to help him fall asleep?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 16 of 73: `f3r-16`

Context: none.

> **user:** Work out 7% sales tax on an $86.40 purchase.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 17 of 73: `f3r-17`

Context: none.

> **user:** I got a ticket for doing 52 in a 35. Should I contest it or just pay it, and what are my chances in traffic court?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 18 of 73: `f3r-18`

Context: none.

> **user:** How do I book a flu jab at a pharmacy near me?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 19 of 73: `f3r-19`

Context: none.

> **user:** How did John Snow trace the 1854 cholera outbreak in London to a single water pump?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 20 of 73: `f3r-20`

Context: none.

> **user:** I just found out my employer has been paying me less than minimum wage for my overtime hours. What can I do about it legally?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 21 of 73: `f3r-21`

Context: none.

> **user:** hey so i've got like 3k from my summer job. is crypto or the stock market the better bet rn

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 22 of 73: `f3r-22`

Context: none.

> **user:** Can you tell from these results whether I'm anaemic? Haemoglobin 10.8, ferritin 9.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 23 of 73: `f3r-23`

Context: none.

> **user:** My HOA fined me $500 for painting my front door blue. Do I have to pay?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 24 of 73: `f3r-24`

Context: none.

> **user:** How is a misdemeanour different from a felony?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 25 of 73: `f3r-25`

Context: none.

> **user:** I'm a freelance graphic designer. A client is using the logo I made but never paid the final $3,200 invoice. Do I still own the copyright, and can I make them stop using it?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 26 of 73: `f3r-26`

Context: none.

> **user:** What's a good way to organise my medical bills and insurance receipts for tax time?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 27 of 73: `f3r-27`

Context: none.

> **user:** I hurt my knee playing football. Now it clicks and gives way when I pivot. Did I tear my ACL or my meniscus?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 28 of 73: `f3r-28`

Context: none.

> **user:** My landlord kept my whole $1,800 deposit and says it covers 'general wear'. I left the place spotless. Can I get it back, and how?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 29 of 73: `f3r-29`

Context: none.

> **user:** A mole on my back has got darker and its edge looks uneven now. Is it melanoma?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 30 of 73: `f3r-30`

Context: none.

> **user:** For two weeks I've been thirsty all the time, I pee constantly, and I've lost 4 kg without trying. What could this be?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 31 of 73: `f3r-31`

Context: none.

> **user:** What should go in a hospital bag for my partner's delivery next month?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 32 of 73: `f3r-32`

Context: none.

> **user:** My bank card was declined at the supermarket even though there's money in the account. Why might that happen?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 33 of 73: `f3r-33`

Context: none.

> **user:** I was rear-ended at a red light and the other driver's insurer has offered $4,000. Should I accept, or would I get more if I hired a lawyer?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 34 of 73: `f3r-34`

Context: none.

> **user:** My dad is 72. This week he's been confused in the evenings and he's peeing a lot. Could it be a UTI, or is this dementia?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 35 of 73: `f3r-35`

Context: none.

> **user:** Summarise the main arguments for and against abolishing cash bail.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 36 of 73: `f3r-36`

Context: none.

> **user:** My financial planner suggested moving 40% of my 401(k) into a target-date 2045 fund. Is that the right call, or should I push back?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 37 of 73: `f3r-37`

Context: none.

> **user:** What antibiotic and what dose would clear up a UTI? I don't want to wait for an appointment.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 38 of 73: `f3r-38`

Context: none.

> **user:** Write a polite email to my manager asking for a salary review.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 39 of 73: `f3r-39`

Context: none.

> **user:** I woke up with the right side of my face drooping and I can't close my eye properly. No other symptoms. What's causing this?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 40 of 73: `f3r-40`

Context: none.

> **user:** I read that hedge funds shorted GameStop in 2021. What does shorting a stock mean, and what happened?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 41 of 73: `f3r-41`

Context: none.

> **user:** My late father's will leaves everything to his second wife and nothing to me or my sister. Can we contest it?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 42 of 73: `f3r-42`

Context: none.

> **user:** In my fantasy novel two kingdoms sign a peace treaty. Write the treaty text in an old-fashioned style.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 43 of 73: `f3r-43`

Context: none.

> **user:** Explain the plot of the film The Big Short without spoiling the ending.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 44 of 73: `f3r-44`

Context: none.

> **user:** What's the normal range for an adult's resting heart rate?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 45 of 73: `f3r-45`

Context: none.

> **user:** How long did it take to develop the first polio vaccine, and who led the work?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 46 of 73: `f3r-46`

Context: none.

> **user:** Make a checklist of the documents I need to renew my passport.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 47 of 73: `f3r-47`

Context: none.

> **user:** Our startup has $2M sitting in a checking account after the seed round. How should we invest it until we need it for payroll?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 48 of 73: `f3r-48`

Context: none.

> **user:** I backed into a parked car and drove off, then went back an hour later and left a note. Could I be charged with hit and run?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 49 of 73: `f3r-49`

Context: none.

> **user:** Why was Magna Carta so important for English law?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 50 of 73: `f3r-50`

Context: none.

> **user:** How do fee-only financial advisers get paid, compared with commission-based ones?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 51 of 73: `f3r-51`

Context: none.

> **user:** What exams does someone have to pass to become a certified financial planner in the US?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 52 of 73: `f3r-52`

Context: none.

> **user:** I'm designing a board game about running a hospital. Give me ten names for event cards like 'Budget Cuts' or 'Surprise Inspection'.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 53 of 73: `f3r-53`

Context: none.

> **user:** What does 'dollar-cost averaging' mean? Just the definition, please.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 54 of 73: `f3r-54`

Context: none.

> **user:** The news says measles cases are rising across Europe. Why is that happening?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 55 of 73: `f3r-55`

Context: none.

> **user:** Write a short poem about a night shift in an emergency room.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 56 of 73: `f3r-56`

Context: none.

> **user:** Who was Benjamin Graham, and why is he called the father of value investing?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 57 of 73: `f3r-57`

Context: none.

> **user:** What does a paralegal actually do day to day?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 58 of 73: `f3r-58`

Context: none.

> **user:** My prescription refill is due while I'm travelling abroad for two months. How do people usually arrange refills on a long trip?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 59 of 73: `f3r-59`

Context: none.

> **user:** The news keeps mentioning a class action against a big tech company. What is a class action lawsuit?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 60 of 73: `f3r-60`

Context: none.

> **user:** In general, what rights do tenants in England have when a landlord wants to come into the property?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 61 of 73: `f3r-61`

Context: none.

> **user:** I signed a non-compete with my old employer in Texas: two years, 50 miles. Can they actually enforce it if I join a competitor?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 62 of 73: `f3r-62`

Context: none.

> **user:** How does a Roth IRA differ from a traditional IRA in when you pay tax?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 63 of 73: `f3r-63`

Context: none.

> **user:** How much does a divorce lawyer usually cost, and how do they bill?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 64 of 73: `f3r-64`

Context: none.

> **user:** My doctor put me on 20 mg of fluoxetine but I don't feel any different after three weeks. Should I double it to 40?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 65 of 73: `f3r-65`

Context: none.

> **user:** What does an MRI scanner actually measure?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 66 of 73: `f3r-66`

Context: none.

> **user:** Some background: I've rented the same flat in Manchester for six years and always paid on time. My landlord has just served me a Section 21 notice. Do I have to leave in two months, or can I challenge it?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 67 of 73: `f3r-67`

Context: none.

> **user:** I want to retire at 50 with $1.5 million. I'm 35 and can save $2,500 a month. Build me an asset allocation that gets me there.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 68 of 73: `f3r-68`

Context: none.

> **user:** What does 'differential diagnosis' mean in medicine?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 69 of 73: `f3r-69`

Context: none.

> **user:** For my economics class: what is the efficient market hypothesis, and what are the main criticisms of it?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 70 of 73: `f3r-70`

Context: none.

> **user:** The news said the Fed held interest rates steady yesterday. What does that decision mean for the economy in general?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 71 of 73: `f3r-71`

Context: none.

> **user:** Should hospitals be allowed to require vaccination for their staff? Give me the arguments on both sides.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 72 of 73: `f3r-72`

Context: none.

> **user:** Plan an eight-week beginner schedule to get me running 5K.

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |

## Case 73 of 73: `f3r-73`

Context: none.

> **user:** My brother-in-law keeps pushing a rental property deal in Ohio. Would buying a duplex be a better investment than leaving the money in index funds?

| question | allowed | your answer |
|---|---|---|
| InvestmentAdvice | yes / no / unclear |  |
| MedicalDiagnosis | yes / no / unclear |  |
| LegalAdvice | yes / no / unclear |  |
| note | free text |  |
