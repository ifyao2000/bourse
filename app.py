from flask import Flask, request
from histo_bourse import scanner_tickers_en_live  # si séparé

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bienvenue sur mon API de scan boursier !'

@app.route('/scanner', methods=['GET'])
def scanner():
    try:
        # Lire les tickers depuis le paramètre URL
        tickers = request.args.get('tickers', '')
        tickers = tickers.split(',') if tickers else ["SLS", "RGTI"]

        scanner_tickers_en_live(
        json_key_path="plasma-set-466417-i4-83ca7c95f947.json",
        nom_fichier_sheet="alerte_bourse",
        nom_feuille="log",
        tickers=["SLS", "RGTI", "LXEO"],
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


        return f"📡 Analyse lancée pour {', '.join(tickers)} !", 200

    except Exception as e:
        return f"Erreur lors de l’analyse : {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
