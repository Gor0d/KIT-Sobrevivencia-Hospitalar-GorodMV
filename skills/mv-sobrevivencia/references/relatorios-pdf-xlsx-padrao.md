# Geração de relatório / PDF (padrão reutilizável)

Vários casos terminam num entregável (planilha + PDF) para faturamento/gestão/jurídico.
Padrão que funciona em ambiente Windows:

- **PDF via navegador headless**: `msedge.exe --headless --disable-gpu --no-pdf-header-footer
  --print-to-pdf=<arquivo>.pdf <arquivo>.html` (Chrome/Edge — o parâmetro é o mesmo). Caminho
  típico do Edge no Windows: `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
  (fallback em `Program Files`).
- Escreva o HTML no diretório de **scratch** e gere o PDF direto num diretório de saída sob
  controle do usuário (ex.: `Downloads`) — o navegador headless às vezes **nega escrita (`Acesso
  negado`)** em certos caminhos (acentuação/espaço); screenshots têm a mesma restrição.
- Não dá para renderizar PDF de volta com um Read tool comum (falta `pdftoppm`) — confira o PDF
  pelo **tamanho do arquivo**, ou gere um screenshot do HTML equivalente.
- **XLSX** com `openpyxl`. Cores por situação, linha de **TOTAL** no rodapé.
- **Logo/cabeçalho institucional**: recrie em HTML/CSS (uma imagem colada no chat não vira
  arquivo) usando a marca e as cores da sua própria instituição — não reaproveite paleta/nome de
  um exemplo de outro hospital.
- Documento sensível (LGPD, financeiro): mantenha como **arquivo local** (não publique como
  artifact/link público), marque **Confidencial / LGPD**, e cite que a base é produção
  somente-leitura.
- **PDF com `reportlab`**: se o cabeçalho colorido é desenhado por `canvas` (banner fixo) mas o
  título é adicionado como *flowable* no `story`, ele pode cair **fora** da faixa colorida (a
  margem do documento começa abaixo do banner) — texto claro em fundo claro (ou vice-versa) fica
  invisível. Desenhe título/subtítulo do banner **direto no canvas** (`canvas.drawString`), nunca
  como flowable, quando o banner também é canvas.

## Comunicação

- Consultas de diagnóstico: cole o SQL direto no chat; reserve arquivos para o que o usuário vai
  guardar/reexecutar.
- Em ação de risco (financeiro, cancelamento, alteração em produção): confirme o alvo, dê o passo
  pela tela + SQL de **validação somente leitura**, e seja honesto sobre limitações (sem horário,
  sem trilha de impressão, etc.) em vez de inventar dado.
