import yfinance as yf
import pandas as pd
import math

def calculer_buckets_succes(
    ticker: str,
    target_percent: float,
    lookahead_days: int,
    bucket_percent: float,
    period: str = "3mo",
    interval: str = "1d"
) -> pd.DataFrame:
    
    # Télécharger les données
    df = yf.download(ticker, period=period, interval=interval).dropna()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[['Close', 'High']].copy()
    
    # Définir les buckets
    min_price = df['Close'].min()
    max_price = df['Close'].max()
    bucket_bounds = []

    current = min_price
    while current < max_price:
        upper = current * (1 + bucket_percent / 100)
        bucket_bounds.append((current, upper))
        current = upper

    # Initialiser la liste des résultats
    bucket_results = []

    # Calculer les essais et réussites par bucket
    for bucket_min, bucket_max in bucket_bounds:
        essais = 0
        reussites = 0

        for i in range(len(df) - lookahead_days):
            price_today = df['Close'].iloc[i]

            if pd.isna(price_today):
                continue

            if bucket_min <= price_today < bucket_max:
                essais += 1
                future_highs = df['High'].iloc[i+1:i+1+lookahead_days]

                if future_highs.isna().any():
                    continue

                target_price = price_today * (1 + target_percent)
                if (future_highs >= target_price).any():
                    reussites += 1

        taux = (reussites / essais) * 100 if essais > 0 else 0.0
        bucket_results.append({
            "bucket": round(bucket_min, 2),  # ✅ Ajout de la valeur numérique du bucket
            "bucket_price": f"[{bucket_min:.2f} à {bucket_max:.2f}]",
            "essais": essais,
            "reussites": reussites,
            "taux_reussite_%": round(taux, 2)
        })

    return pd.DataFrame(bucket_results)

def verifier_prix_live_dans_bucket(ticker: str,
                                    buckets_df: pd.DataFrame,
                                    bucket_size: float,
                                    seuil_succes: float = 70.0) -> None:
    """
    Vérifie si le prix live du ticker est dans un bucket avec taux de succès >= seuil.
    Affiche une alerte si c'est le cas.
    """
    try:
        prix_actuel = yf.Ticker(ticker).info.get("regularMarketPrice")
    except Exception:
        print(f"⛔️ Prix indisponible pour {ticker}")
        return

    if prix_actuel is None:
        print(f"⛔️ Prix introuvable pour {ticker}")
        return

    print(f"\n🔍 {ticker} — Prix actuel : {prix_actuel:.2f}")

    for _, row in buckets_df.iterrows():
        borne_min = row["bucket"]
        borne_max = borne_min + bucket_size
        if borne_min <= prix_actuel < borne_max and row["taux_reussite_%"] >= seuil_succes:
            print(f"🚨 ALERTE : {ticker} est dans {row['bucket_price']} (taux de succès {row['taux_reussite_%']:.1f} %)")
            return

    print(f"❌ Aucun bucket favorable trouvé pour {ticker} au prix actuel.")



import smtplib
import ssl
from email.message import EmailMessage

def envoyer_alerte_email(sujet: str, corps: str,
                         destinataires: list,  # 🆕 liste au lieu d’un seul email
                         expediteur: str,
                         mot_de_passe_app: str) -> None:
    """
    Envoie un courriel via SMTP (par exemple Gmail) à une ou plusieurs personnes.
    """
    msg = EmailMessage()
    msg.set_content(corps)
    msg['Subject'] = sujet
    msg['From'] = expediteur
    msg['To'] = ', '.join(destinataires)  # 🆕 pour gérer plusieurs adresses

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(expediteur, mot_de_passe_app)
        server.send_message(msg)

    print("📬 Email envoyé à :", ', '.join(destinataires))


import yfinance as yf
import pandas as pd
import math
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

import yfinance as yf
import pandas as pd
import math
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

def scanner_tickers_en_live(
    json_key_path: str,
    nom_fichier_sheet: str,
    nom_feuille: str,
    tickers: list,
    bucket_size: float,
    seuil_succes: float,
    delai_expiration_minutes: int,
    destinataires_email: list,
    expediteur_email: str,
    mot_de_passe_app: str,
    target_percent: float,
    lookahead_days: int,
    bucket_percent: float,
    period: str,
    interval: str
):
    """
    Analyse des tickers en temps réel et envoi d'alertes basées sur les buckets de succès.
    """

    # Authentification Google Sheets
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_file(json_key_path, scopes=scope)
    client = gspread.authorize(credentials)
    sheet = client.open(nom_fichier_sheet).worksheet(nom_feuille)

    for idx, ticker in enumerate(tickers, start=1):
        print(f"\n=== 📈 Analyse en cours : {ticker} ===")

        try:
            prix_actuel = yf.Ticker(ticker).info.get("regularMarketPrice")
        except Exception:
            print(f"⛔️ Prix indisponible pour {ticker}")
            continue

        if prix_actuel is None:
            print(f"⛔️ Prix introuvable pour {ticker}")
            continue

        print(f"🔍 {ticker} — Prix actuel : {prix_actuel:.2f}")

        # Calcul des buckets via la fonction analytique
        try:
            df_resultat = calculer_buckets_succes(
                ticker=ticker,
                target_percent=target_percent,
                lookahead_days=lookahead_days,
                bucket_percent=bucket_percent,
                period=period,
                interval=interval
            )
        except Exception as e:
            print(f"❌ Erreur lors du calcul des buckets pour {ticker} : {e}")
            continue

        # Trouver le bucket contenant le prix actuel
        ligne_bucket = df_resultat[df_resultat["bucket_price"].apply(
            lambda label: eval(label.replace("à", ",").replace("[", "(").replace("]", ")")).__contains__(prix_actuel)
        )]

        if not ligne_bucket.empty:
            taux = float(ligne_bucket["taux_reussite_%"].values[0])
            label = ligne_bucket["bucket_price"].values[0]
            bucket_min = ligne_bucket["bucket"].values[0]
            essais = int(ligne_bucket["essais"].values[0])
            reussites = int(ligne_bucket["reussites"].values[0])
        else:
            taux = 0.0
            label = "N/A"
            bucket_min = round(math.floor(prix_actuel / bucket_size) * bucket_size, 2)
            essais = 0
            reussites = 0

        cle_alerte = f"{ticker}:{bucket_min:.2f}"
        maintenant = datetime.now()

        # Vérifier l'historique d'envoi
        historique = sheet.get_all_records()
        alerte_existante = next((x for x in historique if x["alerte"] == cle_alerte), None)
        expiré = (
            alerte_existante is None
            or datetime.strptime(alerte_existante["horodatage"], "%Y-%m-%d %H:%M:%S")
            + timedelta(minutes=delai_expiration_minutes) < maintenant
        )

        if taux >= seuil_succes:
            if expiré:
                print(f"🚨 ALERTE : {ticker} dans {label} (succès {taux:.1f}%)")
                sheet.append_row([
                    maintenant.strftime("%Y-%m-%d %H:%M:%S"),
                    ticker,
                    label,
                    taux,
                    cle_alerte
                ])

                # 💌 Courriel enrichi
                corps = (
                    f"L'action #{idx} — **{ticker}** — a atteint un taux de succès de **{taux:.1f}%** "
                    f"dans le bucket **{label}**, avec un prix actuel de **{prix_actuel:.2f}$**.\n\n"
                    f"📊 **Détail de l'analyse** :\n"
                    f"- Objectif : +{int(target_percent * 100)}% de gain\n"
                    f"- Délai observé : {lookahead_days} jours après l’entrée dans le bucket\n"
                    f"- Données historiques utilisées : {period}, intervalle {interval}\n"
                    f"- Basé sur **{essais} essais** dont **{reussites} réussites**\n"
                    f"- Un essai est considéré comme réussi si, après avoir atteint un prix dans le bucket {label}, "
                    f"le prix a augmenté d’au moins +{int(target_percent * 100)}% dans les {lookahead_days} jours suivants."
                )

                envoyer_alerte_email(
                    sujet=f"🚨 Alerte boursière #{idx} : {ticker} dans le bucket {label}",
                    corps=corps,
                    destinataires=destinataires_email,
                    expediteur=expediteur_email,
                    mot_de_passe_app=mot_de_passe_app
                )

                print(f"📬 Email envoyé à : {', '.join(destinataires_email)}")
            else:
                print(f"⏱ Alerte déjà envoyée récemment pour {cle_alerte}")
        else:
            print(f"📉 Taux trop faible ({taux:.1f}%) dans {label} pour {ticker}")



scanner_tickers_en_live(
    json_key_path="plasma-set-466417-i4-83ca7c95f947.json",
    nom_fichier_sheet="alerte_bourse",
    nom_feuille="log",
    tickers=["SLS", "RGTI"],
    bucket_size=0.5,
    seuil_succes=70.0,
    delai_expiration_minutes=15,
    destinataires_email=["alertebourse1@gmail.com", "autre@gmail.com"],
    expediteur_email="alertebourse1@gmail.com",
    mot_de_passe_app="zsvb yang asup mbdq",
    
    # 🆕 paramètres analytiques
    target_percent=0.1,        # +10%
    lookahead_days=5,          # Sur les 5 prochains jours
    bucket_percent=2.0,        # Buckets de 2%
    period="3mo",              # Fenêtre d'analyse sur 3 mois
    interval="1d"              # Données journalières
)
