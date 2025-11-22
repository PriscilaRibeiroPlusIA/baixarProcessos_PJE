# pje_scraper.py
import os
import time
import traceback
import glob
import re
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
    ElementClickInterceptedException,
    JavascriptException,
    ElementNotInteractableException
)


def configurar_chrome_options_pje(download_path):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=3")

    # <<<< ADIÇÃO IMPORTANTE AQUI >>>>
    # Esta opção desanexa o navegador do script, permitindo que ele permaneça
    # aberto mesmo após o script terminar.
    chrome_options.add_experimental_option("detach", True)

    prefs = {
        "profile.default_content_settings.popups": 0,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False
    }
    # A pasta de download não é mais crítica, mas mantemos a configuração
    if download_path:
        prefs["download.default_directory"] = download_path
        prefs["download.prompt_for_download"] = False
        prefs["download.directory_upgrade"] = True

    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
    )
    return chrome_options


def login_pje_trf3(driver, usuario, senha, pasta_debug):
    url_inicial_trf3_pje = "https://www.trf3.jus.br/pje/acesso-ao-sistema"
    print(f"Navegando para a página inicial de acesso ao PJe TRF3: {url_inicial_trf3_pje}")
    driver.get(url_inicial_trf3_pje);
    time.sleep(3)
    try:
        print("Procurando por botão de aceitar cookies...")
        try:
            b_cookies_xpath = "//button[@data-role='all' and .//span[contains(text(),'Aceitar todos os cookies')]]"
            b_cookies = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, b_cookies_xpath)))
            driver.execute_script("arguments[0].click();", b_cookies);
            print("Botão de cookies clicado.");
            time.sleep(2)
        except:
            print("Botão de aceitar cookies não encontrado/clicável. Prosseguindo...")

        print("Procurando pelo link 'Sistema PJe - 1º Grau'...")
        link_pje_1g_xpath = "//a[contains(@href, 'pje1g.trf3.jus.br') and contains(normalize-space(), 'Sistema PJe - 1º Grau')]"
        link_pje_1g_el = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, link_pje_1g_xpath)))
        sso_url = link_pje_1g_el.get_attribute("href")
        print(f"Link 'Sistema PJe - 1º Grau' encontrado. Navegando para href: {sso_url}")
        if sso_url:
            driver.get(sso_url)
        else:
            print("ERRO: href do link PJe 1G não encontrado."); driver.execute_script("arguments[0].click();",
                                                                                      link_pje_1g_el)

        WebDriverWait(driver, 30).until(EC.url_contains("sso.cloud.pje.jus.br"));
        print(f"Redirecionado para SSO: {driver.current_url}");
        time.sleep(2)
        print("Preenchendo CPF/CNPJ e Senha no SSO...");
        WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "username"))).send_keys(usuario)
        print(f"Usuário (CPF) '{usuario}' inserido.")
        WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.ID, "password"))).send_keys(senha)
        print("Senha inserida.")
        btn_sso = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "kc-login")));
        driver.execute_script("arguments[0].scrollIntoView(true);", btn_sso);
        time.sleep(0.5)
        btn_sso.click();
        print("Botão 'ENTRAR' SSO clicado.")

        print("Aguardando painel PJe (home.seam)...")
        WebDriverWait(driver, 60).until(
            EC.any_of(EC.url_contains("home.seam"), EC.presence_of_element_located((By.ID, "menu"))))
        print(f"Login PJe TRF3 bem-sucedido! URL: {driver.current_url}");
        return True
    except TimeoutException:
        print("ERRO: Timeout durante o processo de login no PJe TRF3.")
        print(f"URL atual no momento do Timeout: {driver.current_url}")
        timestamp = time.strftime('%Y%m%d%H%M%S')
        s_path = os.path.join(pasta_debug, f"debug_pje_login_timeout_{timestamp}.png");
        h_path = os.path.join(pasta_debug, f"debug_pje_login_timeout_{timestamp}.html")
        try:
            driver.save_screenshot(s_path); open(h_path, "w", encoding="utf-8").write(driver.page_source); print(
                f"Debug salvo em: {s_path}")
        except:
            print("Erro ao salvar debug do login.")
        return False
    except Exception as e:
        print(f"ERRO inesperado login PJe: {e}");
        traceback.print_exc()
        timestamp = time.strftime('%Y%m%d%H%M%S')
        s_path = os.path.join(pasta_debug, f"debug_pje_login_erro_{timestamp}.png");
        h_path = os.path.join(pasta_debug, f"debug_pje_login_erro_{timestamp}.html")
        try:
            driver.save_screenshot(s_path); open(h_path, "w", encoding="utf-8").write(driver.page_source); print(
                f"Debug salvo em: {s_path}")
        except:
            print("Erro ao salvar debug do login.")
        return False


def parse_cnj_number_pje(numero_processo_completo: str) -> Optional[dict]:
    numeros_apenas = ''.join(filter(str.isdigit, numero_processo_completo))
    if len(numeros_apenas) == 20:
        return {"sequencial": numeros_apenas[0:7], "digito": numeros_apenas[7:9], "ano": numeros_apenas[9:13],
                "ramo": numeros_apenas[13:14], "tribunal": numeros_apenas[14:16], "origem": numeros_apenas[16:20]}
    else:
        match_cnj_formatado = re.match(r"(\d{1,7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})",
                                       numero_processo_completo.strip())
        if match_cnj_formatado:
            parts = match_cnj_formatado.groups()
            return {"sequencial": parts[0].zfill(7), "digito": parts[1].zfill(2), "ano": parts[2].zfill(4),
                    "ramo": parts[3], "tribunal": parts[4].zfill(2), "origem": parts[5].zfill(4)}
        return None


def format_process_number_for_pje_input(numero_processo_completo: str) -> Optional[str]:
    partes = parse_cnj_number_pje(numero_processo_completo)
    if partes:
        return f"{partes['sequencial']}-{partes['digito']}.{partes['ano']}.{partes['ramo']}.{partes['tribunal']}.{partes['origem']}"
    print(f"    AVISO [PJe]: Não formatou '{numero_processo_completo}' para CNJ. Usando como está.");
    return numero_processo_completo


def access_process_via_quick_search_and_download(driver, numero_processo_planilha, pasta_debug):
    print(f"  [PJe] Tentando acessar processo '{numero_processo_planilha}' via Acesso Rápido para abrir PDF...")
    numero_processo_formatado_para_input = format_process_number_for_pje_input(numero_processo_planilha)
    if not numero_processo_formatado_para_input:
        print(f"    ERRO: Não formatou '{numero_processo_planilha}' para Acesso Rápido.");
        return False

    janela_pje_painel = driver.current_window_handle
    janela_autos_digitais = None

    try:
        pausa_home = 15
        print(f"    Aguardando a página principal (home.seam) assentar completamente ({pausa_home} segundos)...")
        time.sleep(pausa_home)

        # PASSO 1: Tentar clicar no botão "Abrir menu" (Hamburguer)
        print("    Procurando por botão 'Abrir menu'...")
        menu_hamburguer_xpath = "//a[@title='Abrir menu' and contains(@class,'botao-menu')]"
        nav_menu_container_xpath = "//nav[@id='menu']"
        try:
            menu_hamburguer_botao = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, menu_hamburguer_xpath)))
            print(f"    Botão/Link 'Abrir menu' encontrado. Clicando para expandir...")
            driver.execute_script("arguments[0].click();", menu_hamburguer_botao)
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, nav_menu_container_xpath)))
            print("    'Abrir menu' clicado e menu principal agora visível.")
            time.sleep(2)
        except Exception as e_menu_abrir:
            print(f"    AVISO: Problema ao interagir com 'Abrir menu': {e_menu_abrir}. Prosseguindo...")

        # PASSO 2: Localizar e preencher o campo "Acesso rápido"
        acesso_rapido_input_xpath = "//nav[@id='menu']//input[@placeholder='Acesso rápido']"
        acesso_rapido_input = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.XPATH, acesso_rapido_input_xpath)))
        print(f"    Campo 'Acesso rápido' encontrado e visível.")
        driver.execute_script(
            f"arguments[0].value='{numero_processo_formatado_para_input}'; arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));",
            acesso_rapido_input)
        print(f"    Número '{numero_processo_formatado_para_input}' enviado para 'Acesso Rápido'.");
        time.sleep(7)

        # PASSO 3: Clicar na Sugestão "Abrir processo"
        abrir_processo_sugestao_xpath = "//div[contains(@class,'resultado-busca')]//a[contains(@onclick, 'pesquisaRapida')]"
        abrir_processo_link = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, abrir_processo_sugestao_xpath)))
        print("    Sugestão 'Abrir processo' encontrada. Clicando...");
        handles_antes_clique_autos = set(driver.window_handles)
        driver.execute_script("arguments[0].click();", abrir_processo_link)

        # PASSO 4: Lidar com a Nova Aba dos Autos Digitais
        WebDriverWait(driver, 90).until(EC.number_of_windows_to_be(len(handles_antes_clique_autos) + 1))
        janela_autos_digitais = (set(driver.window_handles) - handles_antes_clique_autos).pop()
        driver.switch_to.window(janela_autos_digitais)
        print(f"    Foco na nova aba dos autos: {driver.current_url}")
        WebDriverWait(driver, 45).until(EC.url_contains("Detalhe/listAutosDigitais.seam"));
        print("    Página de detalhes/autos carregada.")

        # PASSO 5: Abrir a página do visualizador de PDF
        print("    Tentando abrir a página de download do PDF...")
        botao_abrir_menu_download_xpath = "//a[@title='Download autos do processo']"
        el_abrir_opcoes = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, botao_abrir_menu_download_xpath)))
        print(f"      Botão inicial de download encontrado. Clicando...");
        driver.execute_script("arguments[0].click();", el_abrir_opcoes);
        time.sleep(2.5)

        botao_intermediario_download_xpath = "//div[contains(@class,'dropdown-menu')]//input[@value='Download']"
        el_intermediario_download = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, botao_intermediario_download_xpath)))
        print(f"      Botão intermediário 'Download' encontrado. Clicando...");
        handles_antes_clique_pdf_viewer = set(driver.window_handles)
        driver.execute_script("arguments[0].click();", el_intermediario_download)

        # PASSO 6: ESPERAR E MUDAR PARA A NOVA ABA/JANELA do visualizador de PDF
        print("      Aguardando nova aba/janela do visualizador de PDF (pje-downloads.trf3.jus.br)...")
        timeout_pdf_viewer_aba = 90
        WebDriverWait(driver, timeout_pdf_viewer_aba).until(
            EC.number_of_windows_to_be(len(handles_antes_clique_pdf_viewer) + 1))
        janela_pdf_viewer = (set(driver.window_handles) - handles_antes_clique_pdf_viewer).pop()
        driver.switch_to.window(janela_pdf_viewer)
        print(f"      Foco na NOVA aba do visualizador de PDF: {driver.current_url}")
        print("      Aguardando página do PDF carregar...");
        time.sleep(15)

        print(f"    SUCESSO: Página do PDF para '{numero_processo_planilha}' aberta para interação manual.")
        return True  # Indica que a página do PDF foi aberta com sucesso

    except Exception as e:
        print(
            f"    ERRO [PJe] Inesperado ao tentar acessar/abrir PDF de '{numero_processo_planilha}': {type(e).__name__} - {e}")
        ts = time.strftime('%Y%m%d%H%M%S')
        s_path = os.path.join(pasta_debug, f"debug_pje_acesso_rapido_erro_{numero_processo_planilha}_{ts}.png")
        try:
            driver.save_screenshot(s_path); print(f"Debug salvo em: {s_path}")
        except Exception as e_debug:
            print(f"Erro ao salvar debug: {e_debug}")
        return False
    finally:
        try:
            if driver and driver.window_handles and janela_pje_painel in driver.window_handles:
                if driver.current_window_handle != janela_pje_painel:
                    driver.switch_to.window(janela_pje_painel)
                print("    Foco retornado para a janela do painel PJe (final da função).")
        except Exception as e_finally:
            print(f"    AVISO: Erro ao focar na janela principal: {e_finally}")