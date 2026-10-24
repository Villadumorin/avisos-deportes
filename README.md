# Avisos de F1, MotoGP e Celta

Notificacións push no móbil:

- **1 hora antes** e **ao comezar** cada sesión de F1 (libres, clasificación, sprint, carreira), de MotoGP (libres, práctica, clasificación, sprint, carreira) e cada partido do Celta (Liga, Copa, Europa…).
- **Os luns ás 09:00**, un resumo da semana: partidos do Celta (rival, competición, día e hora) e se hai GP de F1 ou MotoGP.

Funciona sen o ordenador aceso: execútase gratis en GitHub cada 3 horas e manda os avisos á app **ntfy**.

Fontes: F1 → f1calendar.com · MotoGP → API oficial de motogp.com · Celta → ESPN.

## Instalación (uns 10 minutos)

### 1. App no móbil

1. Instala **ntfy** ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) · [iPhone](https://apps.apple.com/app/ntfy/id1625396347)).
2. Toca **+** e subscríbete a un tema cun nome difícil de adiviñar (calquera que o saiba pode ler os avisos), por exemplo `celta-f1-motogp-x7k2q9`. Apúntao.

### 2. Repositorio en GitHub

1. Crea unha conta en [github.com](https://github.com) se non tes.
2. **New repository** → nome `avisos-deportes` → marca **Private** → *Create repository*.
3. *uploading an existing file* → arrastra `avisos.py` e `README.md` → *Commit changes*.
4. *Add file → Create new file* → como nome escribe `.github/workflows/avisos.yml`, pega dentro o contido dese ficheiro → *Commit changes*.

### 3. Dicirlle o tema de ntfy

*Settings → Secrets and variables → Actions → New repository secret*
- Name: `NTFY_TOPIC`
- Secret: o nome do tema do paso 1 (ex. `celta-f1-motogp-x7k2q9`)

### 4. Probar

*Actions → Avisos deportes → Run workflow* → modo **proba** → *Run workflow*.
Nuns segundos tes que recibir "Proba de avisos" no móbil. Despois lánzao unha vez en modo **programar** e xa queda funcionando só.

## Axustes

Todo está ao principio de `avisos.py`:

- `F1_SESIONS` / `MOTOGP_SESIONS`: quita as sesións das que non queiras aviso (ex. os libres).
- `AVISO_ANTES`: canto antes avisa (1 hora).
- `RESUMO_DIA`, `RESUMO_HORA`: día (0 = luns) e hora do resumo.

## Bo saber

- Os partidos do Celta con hora sen confirmar saen no resumo como "hora por confirmar" e só avisan cando LaLiga fixa a hora.
- Se cambian a hora dunha sesión con menos de 36 h de marxe, pode chegar tamén o aviso coa hora vella.
- Probar no ordenador: `python avisos.py --dry-run` (amosa os avisos sen mandalos) e `python avisos.py --semana` (amosa o resumo desta semana). En Windows precisa antes `pip install tzdata`.
