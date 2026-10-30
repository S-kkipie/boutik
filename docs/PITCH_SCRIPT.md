# Boutik — 3-minute pitch video script

Structure: problem → solution → live demo → impact → security → next steps. Target length **2:50**, hard limit 3:00.

Setup before recording: stack running (`docker compose up --build`), a fresh day (`docker compose down -v && docker compose up --build` if you want clean numbers), Chrome DevTools device mode at **360 × 740**, zoom 100%, notifications off.

## Shot list (English narration)

| Time | Screen | Action | Narration (EN) |
|---|---|---|---|
| 0:00–0:20 | Title slide (`docs/presentation.html`, slide 1) or a photo of a corner shop | — | "In Dakar, the neighbourhood boutique sells bread, rice and sugar all day, in small amounts and in cash. Change is always short, and customers who buy on credit are written in a paper notebook, the *cahier de crédit*." |
| 0:20–0:35 | Problem slide | — | "The notebook gets lost or disputed, nobody can pay a tab remotely, and Bitcoin wallets talk in sats and jargon. The shopkeeper thinks in FCFA." |
| 0:35–0:45 | Login screen | Type PIN `1234` | "This is Boutik: a Lightning till and credit notebook, priced in FCFA, that loads in about 15 kilobytes on a mid-range Android phone." |
| 0:45–1:05 | Caisse | Type `2 pains, 3 cafés Touba et un sucre`, press ➤ | "The shopkeeper just says or types the sale in French. The assistant drafts the cart with the shop's own prices: 1 300 francs. It only drafts; it can never move money." |
| 1:05–1:25 | Payment sheet | Tap **⚡ Encaisser**, then **📱 Simuler le client (démo)** | "One tap shows a Lightning QR. Here a second real LND node plays the customer and pays." *(green screen appears)* "Paid, in about a second. No change to count." |
| 1:25–1:50 | Caisse → ardoise | Type `crédit Moussa 2500 pour riz et huile`, tap **Nouvelle ardoise** → **Enregistrer et envoyer** | "Now the credit notebook. Moussa takes rice and oil on credit. Boutik records 2 500 FCFA and prepares a WhatsApp message with a pay link." |
| 1:50–2:05 | Customer page | Tap **👁 Voir la page du client**, then **📱 Payer avec le portefeuille démo** | "Moussa, or his son in Paris, opens the link. The debt stays in FCFA; the invoice is created at today's rate. Paid, and the tab closes itself." |
| 2:05–2:20 | Journal | Open **Journal** | "At closing time the shopkeeper sees the day: total, Lightning versus cash, top items, and how much is still owed." |
| 2:20–2:35 | Security slide or Portefeuille | Optional: show wrong PIN refused on send | "Security by design: the till uses a macaroon that can only create invoices, so it cannot spend. Sending needs the PIN again and a daily limit. No customer names in invoices or logs." |
| 2:35–2:50 | Impact + next steps slide | — | "Next: signet, a phone-only non-custodial wallet through an LSP, a mobile-money off-ramp partner, and Wolof voice built with native speakers. We want to test it with real boutiques in Dakar." |
| 2:50–3:00 | Repo + demo links | — | "Boutik is open source under MIT. One command, `docker compose up`, and you can try it yourself. Thank you." |

## Version française (narration)

| Temps | Narration (FR) |
|---|---|
| 0:00–0:20 | « À Dakar, la boutique du quartier vend du pain, du riz et du sucre toute la journée, par petites sommes et en espèces. Il manque toujours de la monnaie, et les clients qui prennent à crédit sont notés dans un cahier. » |
| 0:20–0:35 | « Le cahier se perd ou crée des disputes, personne ne peut payer une ardoise à distance, et les portefeuilles Bitcoin parlent en sats. Le boutiquier, lui, pense en FCFA. » |
| 0:35–0:45 | « Voici Boutik : une caisse Lightning et un cahier de crédit, en FCFA, qui se charge en 15 kilo-octets environ sur un Android de milieu de gamme. » |
| 0:45–1:05 | « Le boutiquier dit ou tape la vente en français. L'assistant prépare le panier avec les prix de la boutique : 1 300 francs. Il propose seulement ; il ne peut jamais envoyer d'argent. » |
| 1:05–1:25 | « Un geste et le QR Lightning s'affiche. Ici, un deuxième nœud LND joue le client et paie… Payé, en une seconde. Pas de monnaie à rendre. » |
| 1:25–1:50 | « Maintenant le cahier de crédit. Moussa prend du riz et de l'huile à crédit. Boutik note 2 500 FCFA et prépare un message WhatsApp avec un lien de paiement. » |
| 1:50–2:05 | « Moussa, ou son fils à Paris, ouvre le lien. La dette reste en FCFA ; la facture est créée au taux du jour. Payé, et l'ardoise se ferme toute seule. » |
| 2:05–2:20 | « À la fermeture, le boutiquier voit sa journée : total, Lightning ou espèces, meilleurs articles, et ce qui reste dû. » |
| 2:20–2:35 | « Sécurité dès la conception : la caisse utilise un macaroon qui peut seulement créer des factures, elle ne peut pas dépenser. Pour envoyer, il faut redonner le code et respecter une limite par jour. Aucun nom de client dans les factures ni dans les logs. » |
| 2:35–2:50 | « Prochaines étapes : signet, un portefeuille mobile non-custodial via un LSP, un partenaire de retrait vers le mobile money, et la voix en wolof construite avec des locuteurs natifs. Nous voulons le tester avec de vraies boutiques à Dakar. » |
| 2:50–3:00 | « Boutik est open source, sous licence MIT. Une commande, `docker compose up`, et vous pouvez l'essayer. Merci. » |

Pick one language for the voice track and add subtitles in the other (YouTube auto-translate is not enough for French technical terms; upload an `.srt`).

## Recording tips

- **Screen**: Chrome → DevTools (F12) → device toolbar (Ctrl+Shift+M) → *Responsive* 360 × 740. Hide the DevTools panel by docking it to a separate window, so only the phone frame is recorded.
- **Recorder**: OBS Studio (Window Capture of the Chrome window, 1080p, 30 fps) or the OS screen recorder. Record the voice separately if the room is noisy and merge in any editor.
- **Rehearse once** with the e2e script before recording so the stack is warm: `./scripts/e2e.sh`.
- **Keep it under 3:00.** Cut pauses. If the demo is slow, cut between tap and "Payé" rather than talking over a spinner.
- **Show real things only**: no mockups, no fake numbers. Say "regtest" once so judges know no real money moved.
- **Upload** to YouTube as **Unlisted**, title "Boutik — Lightning till & credit notebook for Dakar boutiques (Dakar Bitcoin Hack 2026)", paste the link in the Devpost form and the README.
