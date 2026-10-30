# Checklist manual — Boutik · Dakar Bitcoin Hack 2026

Para: Adrian Issac Mamani Quispe (Arequipa, Perú).
Cierre: **20 de noviembre de 2026, 20:00 UTC = 15:00 hora de Lima**. Enviar con al menos un día de margen.

---

## 0. ⚠️ BLOQUEANTE: elegibilidad (hacer ANTES de invertir más tiempo)

Las reglas oficiales (https://dakar-bitcoin-hack-2026.devpost.com/rules) dicen:

> "The participants should reside in Africa."

Y la página principal de Devpost indica en "Who can participate":

> "Students only" · "Companies/professional organizations excluded from participation"

Tú resides en Perú y trabajas como ingeniero. Con las reglas tal como están escritas, **podrías no ser elegible para premios**. Antes de grabar el video o seguir puliendo:

- [ ] Enviar el correo de abajo a **contact@dakarbitcoindays.com** (organizadores).
- [ ] Esperar respuesta por escrito y guardarla (captura o PDF).
- [ ] Si la respuesta es "no": decidir entre (a) participar fuera de premios / solo como contribución open-source, o (b) formar un **equipo honesto** con un/a estudiante residente en África que participe de verdad (diseño, pruebas con boutiques reales, pitch en francés/wolof) y figure como miembro real del equipo.
- [ ] **Nunca** declarar una residencia o condición de estudiante que no sea cierta, ni usar a alguien solo como "nombre" para cobrar el premio.

### Borrador de correo (inglés + francés)

**Para:** contact@dakarbitcoindays.com
**Asunto:** Eligibility question — Dakar Bitcoin Hack 2026 / Question d'éligibilité

> Hello,
>
> My name is Adrian Issac Mamani Quispe. I am a software engineer based in Arequipa, Peru, and I am building an open-source project for the Dakar Bitcoin Hack 2026: **Boutik**, a Lightning till and credit notebook for corner shops in Dakar, priced in FCFA (MIT license, regtest MVP with real LND nodes).
>
> The rules page says that "participants should reside in Africa", and the Devpost overview says "Students only". I would like to confirm before submitting:
>
> 1. Can a participant residing outside Africa (Peru) submit a project and be eligible for prizes?
> 2. Can a non-student (working professional, participating as an individual, not on behalf of a company) participate?
> 3. If not, would a team that includes an Africa-resident student as a real team member be eligible?
>
> In any case, the code will remain open source for the community. Thank you for organizing this event.
>
> Best regards,
> Adrian Issac Mamani Quispe
>
> ---
>
> Bonjour,
>
> Je m'appelle Adrian Issac Mamani Quispe, ingénieur logiciel basé à Arequipa (Pérou). Je développe un projet open source pour le Dakar Bitcoin Hack 2026 : **Boutik**, une caisse Lightning et un cahier de crédit pour les boutiques de quartier à Dakar, avec les prix en FCFA (licence MIT, MVP en regtest avec de vrais nœuds LND).
>
> Le règlement indique que « les participants doivent résider en Afrique », et la page Devpost mentionne « Students only ». Avant de soumettre, je voudrais confirmer :
>
> 1. Un participant résidant hors d'Afrique (au Pérou) peut-il soumettre un projet et être éligible aux prix ?
> 2. Une personne qui n'est pas étudiante (professionnel, à titre individuel, sans entreprise) peut-elle participer ?
> 3. Sinon, une équipe comprenant un·e étudiant·e résidant en Afrique, comme vrai membre de l'équipe, serait-elle éligible ?
>
> Dans tous les cas, le code restera open source pour la communauté. Merci pour l'organisation de cet événement.
>
> Cordialement,
> Adrian Issac Mamani Quispe

---

## 1. Lo que Claude NO hizo (te toca a ti)

- Inscribirse en Devpost / registrarse en el hackathon.
- Crear o unirse a un equipo en Devpost.
- Grabar y subir el video.
- Enviar (submit) el proyecto.
- Contactar a los organizadores.

## 2. Inscripción y equipo

- [ ] Resolver el punto 0 (elegibilidad).
- [ ] Registrarte en https://dakar-bitcoin-hack-2026.devpost.com/ con tu cuenta.
- [ ] Si hay compañero/a de equipo, invitarlo desde la página del proyecto en Devpost.

## 3. Repositorio

- [ ] Verificar que el repo es **público** y que `LICENSE` es **MIT**.
- [ ] Verificar que no hay secretos: ni `.env`, ni claves, ni macaroons en el historial (`git log --stat`).
- [ ] Reemplazar en `README.md` el único placeholder que queda: `VIDEO_URL_PLACEHOLDER` (URL y repo ya están puestos).
- [ ] Probar en una máquina limpia: `git clone … && docker compose up --build` → http://localhost:8000 → PIN `1234` → `./scripts/e2e.sh` debe terminar en `All checks passed.`

## 4. Demo pública

- **URL:** https://boutik-demo.santiago-918.workers.dev · PIN `1234` · red regtest (monedas sin valor).
- **Dónde corre:** Cloudflare Containers (Worker `boutik-demo` + contenedor `boutik-demo-boutikdemo`, instancia `basic`, máx. 1), en la cuenta Cloudflare con la que está logueado `wrangler` en esta máquina (santiago@workin2.com).
- **Cómo se comporta:** si nadie la usa 30 min, se duerme. La primera visita la despierta: muestra «Boutik démarre…» y luego «Lightning démarre…» durante ~30–40 s; después funciona normal. Cada vez que despierta arranca con cadena regtest y datos de demo nuevos.
- **Costo:** requiere Workers Paid (la cuenta ya lo tiene, usa otros contenedores). El uso de esta demo cae dentro de la cuota incluida salvo tráfico intenso (≈0,5 GiB‑hora por cada media hora despierta).
- **Re-desplegar tras cambios:** `cd deploy/cloudflare && npm install && npx wrangler deploy`.
- **Probarla de punta a punta:** `E2E_SKIP_DOCKER=1 ./scripts/e2e.sh https://boutik-demo.santiago-918.workers.dev` → debe terminar en `All checks passed.`
- **Apagarla después del hackathon (si quieres):** `cd deploy/cloudflare && npx wrangler delete` (borra el Worker; luego `npx wrangler containers list` y `npx wrangler containers delete <id>`).

- [ ] Abrir la URL de la demo desde el celular (datos móviles, no wifi) un día antes del cierre y otra vez el día del cierre.
- [ ] Recordar: la demo usa regtest, el PIN `1234` es público y cualquiera puede usar los botones de demo. No poner nada real ahí.

## 5. Prueba en un Android real

- [ ] Abrir la app en Chrome Android, "Agregar a pantalla de inicio" (instalar PWA) y abrirla desde el ícono.
- [ ] Probar el micrófono 🎙️ (necesita HTTPS y permiso de micrófono; en local `http://localhost` también funciona).
- [ ] Modo avión: la caja debe abrir y mostrar el aviso "Hors ligne".
- [ ] Probar "Envoyer le lien" → WhatsApp con una ardoise de prueba.

## 6. (Opcional) Modo Claude

- [ ] Crear un archivo `.env` junto a `docker-compose.yml` con `ANTHROPIC_API_KEY=...` (no subirlo al repo; verifica que `.env` esté en `.gitignore`).
- [ ] `docker compose up -d` y comprobar que la caja dice "IA Claude" en vez de "Assistant hors ligne".
- [ ] En una demo pública, considerar el costo: el asistente exige sesión y tiene límite de 20 llamadas por minuto, pero el PIN demo es público. Si no quieres gasto, deja la demo pública sin clave (usa el parser offline).

## 7. Video (máx. 3:00)

- [ ] Seguir `docs/PITCH_SCRIPT.md` (guion en inglés y francés, con tiempos).
- [ ] Grabar a 360 × 740 en Chrome DevTools, OBS o grabador del sistema.
- [ ] Subir a YouTube como **No listado (Unlisted)**.
- [ ] Pegar el link en `README.md` y en Devpost.

## 8. Presentación breve

- [ ] Revisar `docs/presentation.html` (se abre en el navegador; flechas o swipe para pasar).
- [ ] Reemplazar los placeholders de links en la última diapositiva.
- [ ] Si Devpost pide imagen de portada: usar una captura de `docs/screenshots/` (por ejemplo `05-paid.png` o `02-caisse.png`).

## 9. Formulario Devpost

- [ ] Copiar los textos de `docs/SUBMISSION.md` (nombre, tagline, secciones, "Built with").
- [ ] Reemplazar `VIDEO_URL` (repo y demo ya están puestos).
- [ ] Subir 3–5 capturas de `docs/screenshots/`.
- [ ] Revisar ortografía del francés en el resumen.
- [ ] **Enviar antes del 20 nov 2026, 15:00 hora de Lima** (20:00 UTC). Ideal: 19 nov.

## 10. "Build in public"

La página del hackathon pide construir en público y comunicar el avance. Borradores (ajústalos a tu voz; publícalos tú):

**Post 1 (EN, X / nostr)**
> Building Boutik for #DakarBitcoinHack by BTrust: a Lightning till + credit notebook for Dakar corner shops. Prices stay in FCFA, the app loads in ~15 KB on a mid-range Android, and the till's macaroon can only create invoices, never spend. Open source (MIT). ⚡🏪

**Post 2 (FR, X / nostr)**
> Boutik avance : le boutiquier dit « 2 pains et un sucre », l'assistant prépare la vente, le client scanne et c'est « Payé ✓ » en quelques secondes. Les ardoises restent en FCFA et se règlent par un lien WhatsApp. Testé sur de vrais nœuds LND (regtest). #DakarBitcoinHack ⚡

**Post 3 (EN, X / nostr)**
> Security by design in Boutik: least-privilege LND macaroons, PIN re-entry + daily limit for every send, no customer names in invoices or logs, strict CSP. One command to try it: `docker compose up --build`. Repo: https://github.com/S-kkipie/boutik #DakarBitcoinHack #Lightning

## 11. Después del envío

- [ ] Mantener la demo arriba hasta que se anuncien resultados.
- [ ] Responder preguntas de los jueces por email/Devpost.
- [ ] No hacer cambios grandes en `main` después del cierre (si hace falta, usar una rama).
