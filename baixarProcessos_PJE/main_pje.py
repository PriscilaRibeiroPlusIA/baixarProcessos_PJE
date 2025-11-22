# main_pje.py
import os
import time
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
import pje_scraper
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env para o ambiente
load_dotenv()

# --- Variáveis Globais ---
driver_pje_global = None
processos_pje_processados_set = set()


def carregar_log_pje(caminho_log):
    """Carrega os números de processos já processados do arquivo de log."""
    if os.path.exists(caminho_log):
        with open(caminho_log, 'r') as f:
            for line in f:
                processos_pje_processados_set.add(line.strip())
    print(f"{len(processos_pje_processados_set)} processos PJe já constam como processados no log.")


def registrar_processo_concluido_pje(numero_processo, caminho_log):
    """Registra um número de processo como concluído no arquivo de log."""
    with open(caminho_log, 'a') as f:
        f.write(f"{numero_processo}\n")
    processos_pje_processados_set.add(numero_processo)
    print(f"  [Log PJe] Processo '{numero_processo}' marcado como concluído (página do PDF aberta).")


def ler_planilha_pje(caminho_planilha):
    """Lê a planilha, procura pela coluna de processos e retorna uma lista de números de processos válidos."""
    try:
        print(f"Lendo planilha PJe: {caminho_planilha}")
        if not os.path.exists(caminho_planilha):
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho_planilha}")

        # Lê a planilha, usando a primeira linha como cabeçalho
        df = pd.read_excel(caminho_planilha, dtype=str, header=0)

        if df.empty:
            print("AVISO: A planilha PJe está vazia.")
            return []

        # Procura a coluna que contém "processo" no nome (ignorando maiúsculas/minúsculas)
        coluna_processo = None
        for col in df.columns:
            if "processo" in str(col).lower():
                coluna_processo = col
                print(f"    Coluna de processos encontrada: '{coluna_processo}'")
                break

        if coluna_processo is None:
            print("ERRO: Nenhuma coluna com 'processo' no nome foi encontrada na planilha.")
            print(
                "       Verifique se a primeira linha da sua planilha contém o cabeçalho 'Número do Processo' ou similar.")
            return []

        numeros_processos_pje = []
        for valor in df[coluna_processo].dropna():
            num_str = str(valor).strip()
            numeros_apenas = ''.join(filter(str.isdigit, num_str))
            if 15 <= len(numeros_apenas) <= 20:
                numeros_processos_pje.append(numeros_apenas)
            elif num_str:
                print(f"    Valor inválido ou não reconhecido na coluna de processos: '{num_str}'")

        return numeros_processos_pje
    except Exception as e:
        print(f"ERRO ao ler a planilha PJe: {e}")
        return []


def inicializar_driver_pje(pasta_download):
    """Inicializa e retorna o WebDriver para o PJe."""
    global driver_pje_global
    if driver_pje_global is None:
        print("--- Inicializando WebDriver para PJe ---")
        if not os.path.exists(pasta_download):
            os.makedirs(pasta_download)
            print(f"Pasta de download/debug criada em: {pasta_download}")
        else:
            print(f"Pasta de download/debug: {pasta_download}")

        chrome_options_pje = pje_scraper.configurar_chrome_options_pje(pasta_download)
        try:
            driver_pje_global = webdriver.Chrome(options=chrome_options_pje)
            print("Navegador para PJe iniciado.")
        except WebDriverException as e:
            print(f"ERRO ao inicializar o WebDriver para PJe: {e}");
            driver_pje_global = None;
            return None
    return driver_pje_global


def executar_downloads_pje():
    """Função principal para orquestrar o login e a abertura dos PDFs."""
    global driver_pje_global
    print("====================================================")
    print("Iniciando Sistema de Abertura de PDFs PJe TRF3 (via Acesso Rápido)")
    print(f"Data e Hora Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("====================================================")

    pje_user = os.getenv("PJE_USER")
    pje_pass = os.getenv("PJE_PASS")
    apsdj_folder_path = os.getenv("APSDJ_FOLDER_PATH")
    planilha_filename = os.getenv("PLANILHA_FILENAME")
    url_pje_home = os.getenv("URL_PJE_TRF3_HOME", "https://pje1g.trf3.jus.br/pje/home.seam")

    if not all([pje_user, pje_pass, apsdj_folder_path, planilha_filename]):
        print("ERRO CRÍTICO: Variáveis de ambiente não definidas no arquivo .env.");
        return

    caminho_planilha = os.path.join(apsdj_folder_path, planilha_filename)
    pasta_debug_e_download = os.path.join(apsdj_folder_path, "ProcessosBaixadosPJE_TRF3")
    caminho_log = os.path.join(apsdj_folder_path, "pje_trf3_processos_baixados_log.txt")

    numeros_processos_pje_planilha = ler_planilha_pje(caminho_planilha)
    if not numeros_processos_pje_planilha:
        print("Nenhum número de processo válido encontrado na planilha PJe. Encerrando.");
        return

    carregar_log_pje(caminho_log)
    processos_pje_a_processar = [p for p in numeros_processos_pje_planilha if p not in processos_pje_processados_set]

    if not processos_pje_a_processar:
        print("Todos os processos PJe da planilha já foram processados. Encerrando.");
        return

    print(f"Encontrados {len(processos_pje_a_processar)} processos PJe para processar.")
    print(f"Primeiros processos da lista: {processos_pje_a_processar[:5]}")

    driver_pje_global = inicializar_driver_pje(pasta_debug_e_download)
    if not driver_pje_global: print("Falha ao inicializar o navegador para o PJe. Encerrando."); return

    if not pje_scraper.login_pje_trf3(driver_pje_global, pje_user, pje_pass, pasta_debug=pasta_debug_e_download):
        print("Falha no login do PJe. Encerrando.");
        if driver_pje_global: driver_pje_global.quit(); return

    total_processos_pje = len(processos_pje_a_processar)
    for i, num_proc_planilha in enumerate(processos_pje_a_processar):
        print(f"\n===== INICIANDO ABERTURA PJe {i + 1}/{total_processos_pje}: Processo '{num_proc_planilha}' =====")

        if i > 0:
            print(f"--- Navegando para {url_pje_home} para resetar antes do processo {i + 1}/{total_processos_pje} ---")
            try:
                driver_pje_global.get(url_pje_home)
                time.sleep(5)
                print("--- Reset para home.seam concluído ---")
            except Exception as e_gohome:
                print(f"AVISO: Erro ao tentar navegar para home.seam para reset: {e_gohome}")

        pdf_pagina_aberta = pje_scraper.access_process_via_quick_search_and_download(
            driver_pje_global, num_proc_planilha, pasta_debug=pasta_debug_e_download
        )

        if pdf_pagina_aberta:
            print(
                f"SUCESSO NA ABERTURA PJe: Página do PDF para '{num_proc_planilha}' foi aberta para interação manual.")
            registrar_processo_concluido_pje(num_proc_planilha, caminho_log)
        else:
            print(f"FALHA NA ABERTURA PJe: Não foi possível abrir a página do PDF para '{num_proc_planilha}'.")

        pausa_entre_processos = 10
        if i < total_processos_pje - 1:
            print(f"Pausa de {pausa_entre_processos} segundos antes do próximo processo PJe...")
            time.sleep(pausa_entre_processos)

    print("\n----------------------------------------------------")
    print("Todos os processos da planilha PJe foram tentados.")
    print(f"Data e Hora Fim: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("====================================================")
    print("IMPORTANTE: O navegador permanecerá aberto com as abas dos PDFs.")
    print("Você pode fechar esta janela do console. O navegador continuará aberto.")
    print("Script PJe finalizado.")


if __name__ == "__main__":
    try:
        executar_downloads_pje()
    except Exception as e_main:
        print(f"ERRO CRÍTICO no script principal: {e_main}")
        traceback.print_exc()
        # O driver.quit() não é chamado aqui para tentar manter o navegador aberto mesmo em caso de erro.

    # Não há mais código aqui, o script principal simplesmente terminará.
    # O driver.quit() foi removido do fluxo normal.