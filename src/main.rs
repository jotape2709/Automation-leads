//! JPX Lab • Motor Nativo Otimizado em Rust com Integração Python & Cofre Criptográfico (v3.2)
//!
//! Este binário em Rust atua como executável one-click, CLI, supervisor de ambiente
//! e gateway local que consome os módulos analíticos, criptográficos e de IA em Python.

use std::env;
use std::io::{Read, Write};
use std::net::{Shutdown, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

// Paleta ANSI inspirada nas cores da JPX Lab: Vermelho Carmesim, Amarelo Geométrico e Creme
const C_RED: &str = "\x1b[38;2;200;16;46m";
const C_BG_RED: &str = "\x1b[48;2;180;12;32m\x1b[38;2;255;212;38m";
const C_YELLOW: &str = "\x1b[38;2;255;212;38m";
const C_CREAM: &str = "\x1b[38;2;253;248;238m";
const C_MUTED: &str = "\x1b[38;2;180;160;145m";
const C_GREEN: &str = "\x1b[38;2;74;222;128m";
const C_BOLD: &str = "\x1b[1m";
const C_RESET: &str = "\x1b[0m";

fn print_banner() {
    println!();
    println!(
        "  {C_BG_RED}{C_BOLD} ◸◹ JPX LAB {C_RESET} {C_YELLOW}{C_BOLD}AUTOMATION LEADS & CRM v3.2{C_RESET} {C_MUTED}(Rust + Python + AEAD Vault){C_RESET}"
    );
    println!(
        "  {C_RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C_RESET}"
    );
    println!(
        "  {C_CREAM}Prospecção consultiva • Cofre Criptográfico AEAD • Envio sempre manual{C_RESET}"
    );
    println!();
}

/// Resolve o diretório raiz do projeto mesmo quando o executável é aberto por duplo-clique
/// dentro de `target/release` ou a partir de um atalho.
pub fn resolve_base_dir() -> PathBuf {
    let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    if cwd.join("app.py").exists() && cwd.join("static").join("index.html").exists() {
        return cwd;
    }
    if let Ok(exe) = env::current_exe() {
        let mut parent = exe.parent();
        while let Some(dir) = parent {
            if dir.join("app.py").exists() && dir.join("static").join("index.html").exists() {
                return dir.to_path_buf();
            }
            parent = dir.parent();
        }
    }
    cwd
}

/// Localiza o interpretador Python do `.venv` ou do sistema.
pub fn find_python(base_dir: &Path) -> PathBuf {
    let candidates = [
        base_dir.join(".venv").join("bin").join("python"),
        base_dir.join(".venv").join("Scripts").join("python.exe"),
        PathBuf::from("python3"),
        PathBuf::from("python"),
    ];
    for candidate in &candidates {
        if candidate.is_absolute() || candidate.components().count() > 1 {
            if candidate.exists() {
                return candidate.clone();
            }
        } else if Command::new(candidate)
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok()
        {
            return candidate.clone();
        }
    }
    PathBuf::from("python3")
}

/// Garante que o `.venv` exista e possua `pandas` e `openpyxl` instalados antes de subir o servidor.
pub fn ensure_python_environment(base_dir: &Path) -> PathBuf {
    let venv_py = if cfg!(windows) {
        base_dir.join(".venv").join("Scripts").join("python.exe")
    } else {
        base_dir.join(".venv").join("bin").join("python")
    };

    let sys_py = find_python(base_dir);
    let active_py = if venv_py.exists() {
        venv_py.clone()
    } else {
        sys_py.clone()
    };

    let check = Command::new(&active_py)
        .current_dir(base_dir)
        .args(["-c", "import pandas, openpyxl, defusedxml"])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();

    if matches!(check, Ok(s) if s.success()) {
        return active_py;
    }

    println!(
        "  {C_YELLOW}⚙ Preparando ambiente Python otimizado (.venv) no primeiro uso...{C_RESET}"
    );
    if !venv_py.exists() {
        let _ = Command::new(&sys_py)
            .current_dir(base_dir)
            .args(["-m", "venv", ".venv"])
            .status();
    }

    let target_py = if venv_py.exists() { venv_py } else { sys_py };
    let _ = Command::new(&target_py)
        .current_dir(base_dir)
        .args(["-m", "pip", "install", "-q", "-r", "requirements.txt"])
        .status();

    target_py
}

/// Abre o navegador padrão do sistema operacional caso `OPEN_BROWSER` não seja `0`.
pub fn open_browser_url(url: &str) {
    if env::var("OPEN_BROWSER").unwrap_or_else(|_| "1".into()) == "0" {
        return;
    }
    #[cfg(target_os = "windows")]
    {
        let _ = Command::new("cmd")
            .args(["/C", "start", "", url])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn();
    }
    #[cfg(target_os = "macos")]
    {
        let _ = Command::new("open")
            .arg(url)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn();
    }
    #[cfg(target_os = "linux")]
    {
        let _ = Command::new("xdg-open")
            .arg(url)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn();
    }
}

/// Invoca a ponte Python (`python -m prospeccao.bridge`) e retorna a saída JSON bruta.
pub fn call_python_bridge(python: &Path, base_dir: &Path, args: &[&str]) -> Result<String, String> {
    let output = Command::new(python)
        .current_dir(base_dir)
        .args(["-m", "prospeccao.bridge"])
        .args(args)
        .output()
        .map_err(|e| format!("Falha ao executar o motor Python ({:?}): {}", python, e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

    if !output.status.success() && stdout.is_empty() {
        return Err(format!("Erro no motor Python: {}", stderr));
    }
    Ok(stdout)
}

/// Extrai um valor simples de uma chave JSON sem dependências externas.
pub fn extract_json_field(json: &str, key: &str) -> Option<String> {
    let pattern = format!("\"{}\":", key);
    let idx = json.find(&pattern)?;
    let rest = json[idx + pattern.len()..].trim_start();
    if let Some(stripped) = rest.strip_prefix('"') {
        let mut out = String::new();
        let mut escaped = false;
        for ch in stripped.chars() {
            if escaped {
                match ch {
                    'n' => out.push('\n'),
                    't' => out.push('\t'),
                    '"' => out.push('"'),
                    '\\' => out.push('\\'),
                    _ => out.push(ch),
                }
                escaped = false;
            } else if ch == '\\' {
                escaped = true;
            } else if ch == '"' {
                break;
            } else {
                out.push(ch);
            }
        }
        Some(out)
    } else {
        let end = rest
            .find(|c: char| [',', '}', ']'].contains(&c))
            .unwrap_or(rest.len());
        Some(rest[..end].trim().to_string())
    }
}

fn cmd_stats(python: &Path, base_dir: &Path) -> i32 {
    let started = Instant::now();
    match call_python_bridge(python, base_dir, &["stats"]) {
        Ok(json) => {
            let total = extract_json_field(&json, "total_leads").unwrap_or_else(|| "0".into());
            let elegiveis =
                extract_json_field(&json, "whatsapp_elegiveis").unwrap_or_else(|| "0".into());
            let alta = extract_json_field(&json, "prioridade_alta").unwrap_or_else(|| "0".into());
            let hoje = extract_json_field(&json, "contatos_hoje").unwrap_or_else(|| "0".into());
            let limite = extract_json_field(&json, "limite_diario").unwrap_or_else(|| "10".into());
            let followups =
                extract_json_field(&json, "followups_pendentes").unwrap_or_else(|| "0".into());
            let propostas =
                extract_json_field(&json, "propostas_abertas").unwrap_or_else(|| "0".into());
            let fechados = extract_json_field(&json, "fechados").unwrap_or_else(|| "0".into());
            let receita =
                extract_json_field(&json, "receita_fechada").unwrap_or_else(|| "0".into());
            let pipeline =
                extract_json_field(&json, "pipeline_aberto").unwrap_or_else(|| "0".into());
            let arquivo = extract_json_field(&json, "leads_file").unwrap_or_else(|| "—".into());

            println!("  {C_YELLOW}{C_BOLD}📊 RESUMO DO FUNIL COMERCIAL (Rust -> Python IPC){C_RESET}");
            println!("  {C_MUTED}Arquivo base:{C_RESET}       {C_CREAM}{arquivo}{C_RESET}");
            println!(
                "  {C_MUTED}Leads na base:{C_RESET}      {C_CREAM}{C_BOLD}{total}{C_RESET} ({elegiveis} elegíveis para WhatsApp • {alta} prioridade alta)"
            );
            println!(
                "  {C_MUTED}Contatos hoje:{C_RESET}      {C_YELLOW}{C_BOLD}{hoje}/{limite}{C_RESET} {C_MUTED}(limite diário de segurança){C_RESET}"
            );
            println!(
                "  {C_MUTED}Follow-ups hoje:{C_RESET}    {C_RED}{C_BOLD}{followups}{C_RESET} pendentes"
            );
            println!(
                "  {C_MUTED}Propostas ativas:{C_RESET}   {C_CREAM}{C_BOLD}{propostas}{C_RESET} (Pipeline aberto: R$ {pipeline})"
            );
            println!(
                "  {C_MUTED}Clientes fechados:{C_RESET}  {C_GREEN}{C_BOLD}{fechados}{C_RESET} (Receita fechada: {C_YELLOW}{C_BOLD}R$ {receita}{C_RESET})"
            );
            println!(
                "\n  {C_MUTED}⚡ Tempo de resposta IPC Rust->Python: {:?}{C_RESET}\n",
                started.elapsed()
            );
            0
        }
        Err(e) => {
            eprintln!("  {C_RED}✖ {e}{C_RESET}");
            1
        }
    }
}

fn cmd_demo(python: &Path, base_dir: &Path) -> i32 {
    println!("  {C_YELLOW}⚙ Gerando base demonstrativa do ABC Paulista e exemplos no funil CRM...{C_RESET}");
    match call_python_bridge(python, base_dir, &["seed-demo"]) {
        Ok(json) => {
            let total = extract_json_field(&json, "total_leads").unwrap_or_else(|| "14".into());
            let arq = extract_json_field(&json, "arquivo")
                .unwrap_or_else(|| "Leads_ABC_Paulista.xlsx".into());
            println!(
                "  {C_GREEN}{C_BOLD}✔ Base criada com sucesso:{C_RESET} {C_CREAM}{total} leads exportados para {arq}{C_RESET}\n"
            );
            cmd_stats(python, base_dir)
        }
        Err(e) => {
            eprintln!("  {C_RED}✖ Falha ao gerar base demo: {e}{C_RESET}");
            1
        }
    }
}

fn cmd_generate(python: &Path, base_dir: &Path, extra: &[String]) -> i32 {
    let empresa = extra
        .first()
        .map(|s| s.as_str())
        .unwrap_or("Barbearia Dom Imperial");
    let segmento = extra.get(1).map(|s| s.as_str()).unwrap_or("Barbearia");
    let cidade = extra.get(2).map(|s| s.as_str()).unwrap_or("Santo André");
    let servico = extra
        .get(3)
        .map(|s| s.as_str())
        .unwrap_or("Landing Page Express — R$ 149");

    println!(
        "  {C_YELLOW}✍ Solicitando abordagem ao motor Python para:{C_RESET} {C_CREAM}{C_BOLD}{empresa}{C_RESET} ({segmento} • {cidade})"
    );
    match call_python_bridge(
        python,
        base_dir,
        &[
            "generate",
            "--empresa",
            empresa,
            "--segmento",
            segmento,
            "--cidade",
            cidade,
            "--servico",
            servico,
        ],
    ) {
        Ok(json) => {
            let ctx = extract_json_field(&json, "contexto").unwrap_or_default();
            let msg = extract_json_field(&json, "mensagem").unwrap_or_default();
            println!("\n  {C_RED}{C_BOLD}▸ CONTEXTO ESTRATÉGICO:{C_RESET}");
            println!("  {C_MUTED}{ctx}{C_RESET}\n");
            println!("  {C_YELLOW}{C_BOLD}▸ MENSAGEM REVISÁVEL (WHATSAPP):{C_RESET}");
            println!("  {C_CREAM}────────────────────────────────────────────────────────{C_RESET}");
            for line in msg.lines() {
                println!("  {C_CREAM}{line}{C_RESET}");
            }
            println!("  {C_CREAM}────────────────────────────────────────────────────────{C_RESET}\n");
            0
        }
        Err(e) => {
            eprintln!("  {C_RED}✖ {e}{C_RESET}");
            1
        }
    }
}

fn cmd_doctor(python: &Path, base_dir: &Path) -> i32 {
    println!("  {C_YELLOW}{C_BOLD}🛡️  DIAGNÓSTICO DE SEGURANÇA E AMBIENTE (JPX DOCTOR){C_RESET}");
    println!("  {C_MUTED}Interpretador Python:{C_RESET} {C_CREAM}{:?}{C_RESET}", python);
    match call_python_bridge(python, base_dir, &["doctor"]) {
        Ok(json) => {
            let py_ver = extract_json_field(&json, "python_version").unwrap_or_default();
            let ok = extract_json_field(&json, "ok").unwrap_or_default();
            println!("  {C_MUTED}Versão do Python:{C_RESET}     {C_CREAM}{py_ver}{C_RESET}");
            println!(
                "  {C_MUTED}Varredura de segredos:{C_RESET} {}",
                if ok == "true" {
                    format!("{C_GREEN}{C_BOLD}✔ Limpo (0 vazamentos){C_RESET}")
                } else {
                    format!("{C_RED}{C_BOLD}✖ Problemas detectados{C_RESET}")
                }
            );
        }
        Err(e) => {
            eprintln!("  {C_RED}✖ Erro ao executar ponte Python: {e}{C_RESET}");
            return 1;
        }
    }

    println!("\n  {C_YELLOW}🧪 Executando suíte de testes automatizados Python...{C_RESET}");
    let status = Command::new(python)
        .current_dir(base_dir)
        .args(["-m", "unittest", "discover", "-s", "tests", "-v"])
        .status();

    match status {
        Ok(s) if s.success() => {
            println!(
                "\n  {C_GREEN}{C_BOLD}✔ Todos os testes e verificações passaram com sucesso!{C_RESET}\n"
            );
            0
        }
        _ => {
            eprintln!("\n  {C_RED}✖ Falha na suíte de testes.{C_RESET}\n");
            1
        }
    }
}

/// Proxy reverso TCP/HTTP em Rust que encaminha tráfego local para o worker Python
/// validando loopback e registrando telemetria de latência.
fn proxy_connection(mut client: TcpStream, backend_port: u16, frontend_port: u16) {
    let started = Instant::now();
    let _ = client.set_read_timeout(Some(Duration::from_secs(30)));
    let _ = client.set_write_timeout(Some(Duration::from_secs(30)));

    let peer_ok = client
        .peer_addr()
        .map(|addr| addr.ip().is_loopback())
        .unwrap_or(false);
    if !peer_ok {
        let _ = client.write_all(
            b"HTTP/1.1 403 Forbidden\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"error\":\"Acesso restrito a loopback pelo motor Rust.\"}"
        );
        return;
    }

    let mut req_buf = vec![0u8; 65536];
    let n = match client.read(&mut req_buf) {
        Ok(0) | Err(_) => return,
        Ok(n) => n,
    };
    req_buf.truncate(n);

    let req_str = String::from_utf8_lossy(&req_buf);
    let first_line = req_str.lines().next().unwrap_or("REQUEST").to_string();
    let rewritten = req_str
        .replace(
            &format!("localhost:{frontend_port}"),
            &format!("127.0.0.1:{backend_port}"),
        )
        .replace(
            &format!("127.0.0.1:{frontend_port}"),
            &format!("127.0.0.1:{backend_port}"),
        )
        .replace("Connection: keep-alive", "Connection: close")
        .replace("connection: keep-alive", "Connection: close");

    let mut backend = match TcpStream::connect(("127.0.0.1", backend_port)) {
        Ok(s) => s,
        Err(_) => {
            let _ = client.write_all(
                b"HTTP/1.1 502 Bad Gateway\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"error\":\"Worker Python indisponivel.\"}"
            );
            return;
        }
    };
    let _ = backend.set_read_timeout(Some(Duration::from_secs(60)));
    if backend.write_all(rewritten.as_bytes()).is_err() {
        return;
    }
    let _ = backend.shutdown(Shutdown::Write);

    let mut resp_buf = Vec::new();
    if backend.read_to_end(&mut resp_buf).is_ok() {
        let _ = client.write_all(&resp_buf);
    }
    let elapsed = started.elapsed();
    println!(
        "  {C_RED}[RUST-GW]{C_RESET} {C_CREAM}{first_line}{C_RESET} {C_YELLOW}({:.2?}){C_RESET}",
        elapsed
    );
}

struct WorkerGuard(Child);
impl Drop for WorkerGuard {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

fn find_free_port(start: u16) -> u16 {
    for p in start..start.saturating_add(30) {
        if TcpListener::bind(("127.0.0.1", p)).is_ok() {
            return p;
        }
    }
    start
}

fn cmd_serve(python: &Path, base_dir: &Path, requested_port: u16, auto_demo: bool) -> i32 {
    let leads_path = base_dir.join("Leads_ABC_Paulista.xlsx");
    if auto_demo || !leads_path.exists() {
        println!(
            "  {C_YELLOW}⚡ Preparando base inicial de leads para abertura imediata...{C_RESET}"
        );
        let _ = call_python_bridge(python, base_dir, &["seed-demo"]);
    }

    // Se a porta solicitada já estiver em execução com o CRM, apenas abre o navegador!
    if TcpStream::connect(("127.0.0.1", requested_port)).is_ok() {
        let url = format!("http://127.0.0.1:{requested_port}");
        println!(
            "  {C_GREEN}{C_BOLD}✔ Instância do CRM JPX Lab já está ativa em:{C_RESET} {C_YELLOW}{C_BOLD}{url}{C_RESET}"
        );
        open_browser_url(&url);
        return 0;
    }

    let port = find_free_port(requested_port);
    let backend_port = find_free_port(port.saturating_add(1));

    println!(
        "  {C_MUTED}▸ Iniciando worker Python seguro em{C_RESET} {C_CREAM}127.0.0.1:{backend_port}{C_RESET}"
    );
    let child = match Command::new(python)
        .current_dir(base_dir)
        .env("APP_PORT", backend_port.to_string())
        .env("OPEN_BROWSER", "0")
        .env("AUTO_SEED_DEMO", "1")
        .arg(base_dir.join("app.py"))
        .stdout(Stdio::null())
        .stderr(Stdio::inherit())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            eprintln!("  {C_RED}✖ Falha ao iniciar worker Python: {e}{C_RESET}");
            return 1;
        }
    };
    let _guard = WorkerGuard(child);

    for _ in 0..50 {
        if TcpStream::connect(("127.0.0.1", backend_port)).is_ok() {
            break;
        }
        thread::sleep(Duration::from_millis(80));
    }

    let listener = match TcpListener::bind(("127.0.0.1", port)) {
        Ok(l) => l,
        Err(e) => {
            eprintln!(
                "  {C_RED}✖ Não foi possível abrir a porta 127.0.0.1:{port}: {e}{C_RESET}"
            );
            return 1;
        }
    };

    let url = format!("http://127.0.0.1:{port}");
    println!(
        "  {C_GREEN}{C_BOLD}🚀 Gateway Rust + Cofre AEAD + CRM ativo em:{C_RESET} {C_YELLOW}{C_BOLD}{url}{C_RESET}"
    );
    println!(
        "  {C_MUTED}   Pressione Ctrl+C para encerrar o servidor com segurança.{C_RESET}\n"
    );

    open_browser_url(&url);

    for stream in listener.incoming().flatten() {
        thread::spawn(move || {
            proxy_connection(stream, backend_port, port);
        });
    }
    0
}

fn print_help() {
    println!("  {C_YELLOW}{C_BOLD}USO:{C_RESET}");
    println!("    {C_CREAM}cargo run --release -- [COMANDO] [OPÇÕES]{C_RESET}\n");
    println!("  {C_YELLOW}{C_BOLD}COMANDOS DISPONÍVEIS:{C_RESET}");
    println!(
        "    {C_RED}{C_BOLD}serve{C_RESET} [--port 8765] [--demo]  Inicia o Gateway Rust + Painel CRM Web (padrão)"
    );
    println!(
        "    {C_RED}{C_BOLD}demo{C_RESET}                          Gera planilha de leads de exemplo e popula o funil"
    );
    println!(
        "    {C_RED}{C_BOLD}stats{C_RESET}                         Exibe métricas em tempo real do funil no terminal"
    );
    println!(
        "    {C_RED}{C_BOLD}generate{C_RESET} [empresa] [segmento] Gera abordagem consultiva via motor Python"
    );
    println!(
        "    {C_RED}{C_BOLD}collect{C_RESET}                       Executa coleta via Google Places API (index.py)"
    );
    println!(
        "    {C_RED}{C_BOLD}doctor{C_RESET}                        Audita segurança do repositório e executa testes\n"
    );
}

fn main() {
    print_banner();
    let base_dir = resolve_base_dir();
    let python = ensure_python_environment(&base_dir);
    let args: Vec<String> = env::args().skip(1).collect();
    let cmd = args.first().map(|s| s.as_str()).unwrap_or("serve");

    let code = match cmd {
        "serve" | "start" | "run" => {
            let mut port: u16 = env::var("APP_PORT")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(8765);
            let mut demo = false;
            let mut i = 1;
            while i < args.len() {
                match args[i].as_str() {
                    "--port" | "-p" => {
                        if let Some(val) = args.get(i + 1) {
                            port = val.parse().unwrap_or(port);
                            i += 1;
                        }
                    }
                    "--demo" => demo = true,
                    _ => {}
                }
                i += 1;
            }
            cmd_serve(&python, &base_dir, port, demo)
        }
        "demo" | "seed" => cmd_demo(&python, &base_dir),
        "stats" | "status" => cmd_stats(&python, &base_dir),
        "generate" | "pitch" => cmd_generate(&python, &base_dir, &args[1..]),
        "collect" => {
            let status = Command::new(&python)
                .current_dir(&base_dir)
                .arg(base_dir.join("index.py"))
                .status();
            match status {
                Ok(s) => s.code().unwrap_or(0),
                Err(e) => {
                    eprintln!("  {C_RED}✖ Erro ao executar index.py: {e}{C_RESET}");
                    1
                }
            }
        }
        "doctor" | "check" | "test" => cmd_doctor(&python, &base_dir),
        "--help" | "-h" | "help" => {
            print_help();
            0
        }
        _ => {
            eprintln!("  {C_RED}Comando desconhecido: {cmd}{C_RESET}\n");
            print_help();
            1
        }
    };

    std::process::exit(code);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_json_field_strings_and_numbers() {
        let sample = r#"{"ok": true, "total_leads": 14, "leads_file": "Leads_ABC_Paulista.xlsx", "mensagem": "Linha 1\nLinha 2"}"#;
        assert_eq!(extract_json_field(sample, "ok"), Some("true".to_string()));
        assert_eq!(
            extract_json_field(sample, "total_leads"),
            Some("14".to_string())
        );
        assert_eq!(
            extract_json_field(sample, "leads_file"),
            Some("Leads_ABC_Paulista.xlsx".to_string())
        );
        assert_eq!(
            extract_json_field(sample, "mensagem"),
            Some("Linha 1\nLinha 2".to_string())
        );
    }

    #[test]
    fn test_find_python_returns_valid_path() {
        let py = find_python(Path::new("."));
        assert!(!py.as_os_str().is_empty());
    }

    #[test]
    fn test_resolve_base_dir_finds_project_root() {
        let root = resolve_base_dir();
        assert!(root.join("app.py").exists());
    }
}
