# 🧩 Analisi Network

## Contesto e obiettivo

Lo script nasce dall’esigenza di **automatizzare e integrare i dati funzionali del cliente** in una **estrazione tecnica grezza del traffico di rete** (esportata in .csv) di **tutte le virtual machines** nel perimetro di migrazione nei **cluster on-premises VMware**, al fine di **individuare con precisione l’insieme minimo di regole firewall necessarie** a garantire il funzionamento dei workload una volta **migrati su infrastruttura Cloud Azure**.

> In pratica: trasformiamo dati tecnici eterogenei (IP, porte, flussi, applicazioni, servizi) in **requisiti di connettività** chiari, verificabili e tracciabili per i team **network/security** e **cloud**.

### Perché è cruciale per il progetto “Go to Cloud – Wave 4”

Questa attività è **tra le più critiche** per il successo della migrazione su nuova **infrastruttura Cloud** perché spostare i server del cliente senza **un’analisi di connettività affidabile** comporta rischi elevati (servizi non raggiungibili, comunicazioni interrotte, rollback, ritardi, incidenti).

### Flusso di lavoro (alto livello)

1. **Fonti dati**

   * Report Flexera ( CSV con flussi network - *src, dest, ports, etc.*).
   * Metadati cliente (grouping logico, servizi condivisi, subnet e porte note, etc.).

2. **Elaborazione**
   * **Filtro** sulla *Wave4* (`src_group` / `dest_group`).
   * **Arricchimento** per identificare la posizione logica (**location/subnet**) e il servizio noto di ciascun IP sorgente e destinazione. Mapping **IP→servizio**, **subnet→location** (longest-prefix match), normalizzazione location.
   * **Classificazione porte note** per generare **commenti** utili alla stesura delle regole network e requisiti.

3. **Output**
   * **CSV** consolidato con colonne aggiuntive (`src_service`, `dest_service`, `src_loc`, `dest_loc`, `COMMENTO`) cruciali che supportano significativamente e diventano parte integrante dei **parametri** su cui basare i **requisiti network** per Cloud Azure.

4. **Ciclo iterativo**
   * Condivisione con **Security/Cloud** → feedback → implementazione requisiti network → aggiornamento mapping/normalizzazioni → nuova analisi.

---

## Anteprima

![Applicazione](https://github.com/angelomartino/Analisi-Network---Nutella-Edition---Data-Analyst/blob/main/img/interface.png?raw=true)

Lo sviluppo di questa applicazione ha beneficiato del supporto di diversi modelli linguistici di intelligenza artificiale LLM, impiegati per attività di stesura e documentazione.
Ogni sezione del codice è stata comunque attentamente revisionata e consolidata dall’autore per garantirne l’accuratezza e l’aderenza agli obiettivi.

## 🗂️ File richiesti

### 1. Report Flexera (CSV)
Si tratta del file *detailed_application_dependency_data.CSV*, contenente i dati tecnici sul traffico di rete esportati da Flexera, un’applicazione **agentless** (cioè che non richiede l’installazione di componenti sui server) utilizzata per raccogliere e monitorare in modo centralizzato tutte le comunicazioni di rete tra le macchine virtuali.
Deve includere almeno le colonne:

- `src_name`, `dest_name`
- `src_addr`, `dest_addr`
- `src_group`, `dest_group`
- `dest_port`

### 2. File Excel (obbligatorio)
File `.xlsx` con due fogli denominati esattamente:

#### 🧱 Foglio `location`
| location | subnet |
|----------|--------|
| ALBA_AUT NET | 10.11.12.13/16 |
| ALBA_DMZ EXT | 10.11.12.13/27 |
| ... | ... |

Da questo foglio viene costruito il dizionario python:
```python
LOCATION_TO_SUBNETS = {
  'ALBA_AUT NET': ['10.11.12.13/16', '10.11.12.13/20'],
  'ALBA_DMZ EXT': ['10.11.12.13/27'],
  ...
}
```

#### ⚙️ Foglio `servizi`
| servizio | hostname | ip_address |
|----------|----------|------------|
| LoadBalancer | lb01 | 10.11.12.13 |
| Domain Controller | dc01 | 10.11.12.14 |
| Veeam | ve01 | 10.11.12.15 |
| ... | ... | ... |

Da questo foglio viene costruito il dizionario:
```python
SERVIZIO_TO_IPS = {
  'LoadBalancer': ['10.11.12.13'],
  'Monitoring': ['10.11.12.14', '10.11.12.15'],
  ...
}
```
\
I due dizionari rappresentano la mappatura tra le diverse location/servizi. Entrambi verrano successivamente ottimizzati per consentire operazioni di lookup in tempo costante (O(1)) durante le fasi di elaborazione dei dati di rete.

---

## ⚙️ Flusso di elaborazione

1. L'utente seleziona il report CSV e l'Excel con i mapping.

2. Alla pressione del pulsante **Esegui**:
   - Il programma legge l'Excel, costruisce:
     - `SERVIZIO_TO_IPS`
     - `LOCATION_TO_SUBNETS`
   - Viene aperto il CSV originale.
   - Per ogni riga del CSV:
     - Vengono applicati i filtri (Wave, Server, "self-talking" escluso).
     - Ogni IP sorgente/destinazione viene:
       - Arricchito con il servizio (`src_service`, `dest_service`)
       - Arricchito con la location (`src_loc`, `dest_loc`)
     - Se rilevati pattern particolari di porte (es. 25, 8080, 10065, 383, etc.), viene aggiunto un commento automatico.

3. Il CSV finale arricchito viene salvato nella stessa cartella con nome:
```
   nutella_YYYY-MM-DD_HH-MM-SS.csv
```

4. Alla fine, nella console vengono mostrati:
   - Stato di completamento
   - Riepilogo del numero di righe elaborate
   - Conteggio traffico **outbound/inbound** per ciascun server filtrato

---

## 🧾 Colonne aggiunte nel CSV finale

| Colonna | Descrizione |
|---------|-------------|
| `src_service` | Servizio associato all'indirizzo IP sorgente |
| `dest_service` | Servizio associato all'indirizzo IP di destinazione |
| `src_loc` | Location derivata dal subnet matching per IP sorgente |
| `dest_loc` | Location derivata dal subnet matching per IP destinazione |
| `COMMENTO` | Commento automatico (es. SMTP, Proxy, Zscaler, skip shared services) |

---

## 🧱 Logica delle regole rilevate automaticamente

| Porta | Commento |
|-------|----------|
| 25 | SMTP |
| 8080 | Proxy |
| 10065 | Zscaler |
| 383 | Rule OMI |
| Altri casi | "Shared Services" se coinvolgono IP di servizi noti |
| ... | ... |

---

## 📦 Output di esempio

Esempio di output generato (semplificato):
```csv
src_name,dest_name,src_addr,dest_addr,src_service,dest_service,src_loc,dest_loc,COMMENTO
SRV01,SRV02,10.11.12.13,10.11.14.15,8080,LoadBalancer,Monitoring,ALBA_AUT NET,ALBA_DMZ EXT,skip shared services
SRV03,SRV04,10.11.12.99,10.11.13.77,25,unknown,unknown,ALBA_DMZ INT,ALBA_DMZ EXT,SMTP
```

Features originali report Flexera:
```csv
src_name,src_group,src_loc,src_addr,src_port,dest_name,dest_group,dest_loc,dest_addr,dest_port,protocol_name,netstat_count,src_proc,src_app,src_app_context,src_app_instance,dest_proc,dest_app,dest_app_context,dest_app_instance,first_seen,last_seen,critical,src_stack_tags,dest_stack_tags,src_device_tags,dest_device_tags
```
---

## 💬 Note finali

Questo strumento è una componente cruciale nella pipeline di migrazione "Go To Cloud Wave 4", in quanto consente di:

- automatizzare l'enrichment dei dati di rete
- ridurre l'errore umano nella definizione delle regole firewall
- produrre requisti coerenti, validati e tracciabili per i team network/security. architetturale.

Sebbene lo script sia progettato per rilevare in modo automatico la maggior parte dei requisiti di connettività necessari al corretto funzionamento delle macchine virtuali, il suo valore principale risiede nella fase di analisi condivisa.

L’elaborato finale generato dallo script (contenente l’elenco delle regole firewall e dei flussi di rete rilevati) viene infatti sottoposto al team di networking per una revisione congiunta.
In questa fase, vengono approfonditi e validati i flussi che richiedono ulteriori verifiche tecniche o chiarimenti applicativi, così da garantire che tutte le dipendenze siano correttamente comprese e gestite nel processo di migrazione verso Azure.

## Licenza
© 2025 Angelo Martino. Tutti i diritti riservati.  
Il codice è pubblicato esclusivamente a scopo dimostrativo e non è autorizzato l'uso, la modifica o la ridistribuzione senza consenso scritto dell'autore.
