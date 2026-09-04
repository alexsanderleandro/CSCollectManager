# Assinatura do ZIP de contagens — como é gerada e como validar no ERP (VB6)

Documento para o programador do ERP retaguarda (VB6). Explica **como o LogScan
assina** o arquivo de contagens e **como validar essa assinatura no VB6** antes
de importar, garantindo que o arquivo não foi alterado.

O código VB6 da seção 6 foi validado: as chamadas de CryptoAPI abaixo foram
testadas contra um `.db` real assinado pelo app, confirmando aceitação do
arquivo íntegro e rejeição de um arquivo com 1 byte alterado.

A **seção 7 traz um exemplo completo** com dois arquivos reais — uma exportação
íntegra e uma com `qtdecontada` alterada por SQL — incluindo os hashes e o
resultado esperado de cada uma. Use esses dois ZIPs como caso de teste da
rotina antes de ligá-la na importação.

---

## 1. O que vem no ZIP

```
CONTAGEM_1_014_04671382000136_040920261100.zip
├── CONTAGEM_..._070520261714.db            ← contagens (SQLite) — é o que o ERP importa
├── CONTAGEM_..._070520261714.pdf           ← relatório para conferência humana
├── CONTAGEM_..._070520261714.sig           ← assinatura (JSON)
├── CONTAGEM_..._070520261714_metricas.enc  ← métricas cifradas (opcional, ignorar)
└── fotos/                                   ← fotos de produtos (opcional)
```

O ERP precisa apenas de **dois** arquivos: o `.db` e o `.sig`. Os demais podem
ser ignorados.

---

## 2. Como a assinatura é gerada (lado do app)

Código-fonte: `security/export_db_signing.py` (funções `assinar_db` e `montar_sig`).

O `.sig` carrega **duas assinaturas independentes, com propósitos diferentes**:

| Campo | Algoritmo | Para quê | O ERP usa? |
|---|---|---|---|
| `assinatura` | HMAC-SHA256 (chave = token da licença) | Provar para a CSCollectAPI que o upload veio de um aparelho ativado | **Não** |
| `assinatura_rsa` | RSA-2048 / PKCS#1 v1.5 / SHA-256 | Provar que o `.db` é genuíno, offline | **Sim — é esta** |

**Ignore o campo `assinatura` (HMAC).** Ele usa uma chave simétrica que o ERP
não tem (e não deve ter). A assinatura que interessa é a `assinatura_rsa`.

### Por que RSA e não HMAC para o ERP

Com HMAC, a mesma chave assina e verifica. Se ela fosse embutida no ERP,
qualquer um que a extraísse poderia forjar um `.db` com quantidades alteradas
e o ERP aceitaria. Com RSA há um par de chaves:

- **chave privada** — só existe dentro do app LogScan, nunca é distribuída;
- **chave pública** — embutida no ERP, só serve para *verificar*, não para assinar.

Ou seja: mesmo alguém com acesso total ao código do ERP não consegue produzir
um `.db` que passe na validação.

### Passos exatos que o app executa

```
1. Gera o arquivo .db com as contagens
2. hash_db       = SHA-256(bytes crus do .db)                        → hex
3. assinatura_rsa = RSA_Sign_PKCS1v15_SHA256(bytes do .db, chave privada) → Base64
4. Monta o JSON do .sig com hash_db no payload e assinatura_rsa na raiz
5. Empacota .db + .pdf + .sig (+ fotos) no ZIP
```

Detalhe importante: a assinatura é feita sobre os **bytes crus do arquivo `.db`
inteiro**, não sobre o conteúdo lógico das tabelas. Qualquer alteração no
arquivo — inclusive abrir e salvar num editor SQLite sem mudar dado algum —
altera os bytes e invalida a assinatura.

---

## 3. Formato do `.sig`

JSON UTF-8, indentado, chaves em ordem alfabética. Exemplo real (assinatura
truncada para caber):

```json
{
  "assinatura": "2e472c4f41805cffdb99aca0ca3a2ac8212c3b90fad35076632e908028138af1",
  "assinatura_rsa": "ysQNSVUuk09T+KEVhQeU0R/WHZxgwfQHsHv1JQy/4AU30Yciv...Pvr0xQ==",
  "payload": {
    "algoritmo": "HMAC-SHA256",
    "algoritmo_rsa": "RSA-2048/PKCS1v15-SHA256",
    "cnpj": "65381113000120",
    "codempresa": "1",
    "codvendedor": "043",
    "hash_assinatura": "3a4fae999aeeda66ac91526304da752f420e2714a41f986eb0097f4945e05145",
    "hash_db": "2fab990b5d18ca53b9b04488030ee2e6e733bd81eeaabacf9a4d5eabc904b90a",
    "hash_fotos": { "fotos/7891.jpg": "2fab990b5d18ca..." },
    "hash_metricas": "",
    "hash_pdf": "",
    "idcelular": "97fe33f6f301aa86",
    "modelo": "CONTAGEM",
    "nome_arquivo": "CONTAGEM_1_014_04671382000136_040920261100.zip",
    "serial": "TOKEN_LICENCA_EXEMPLO",
    "timestamp": "2026-05-07T17:14:00",
    "versao": "1.4.2"
  }
}
```

Os dois campos que o ERP lê:

- `assinatura_rsa` (raiz) — Base64, 256 bytes depois de decodificado.
- `payload.hash_db` — SHA-256 hex do `.db` (64 caracteres).

Os demais campos são informativos (podem ser úteis para log/auditoria no ERP:
CNPJ, vendedor, data/hora, versão do app, id do aparelho).

> **Atenção — o que a assinatura RSA cobre e o que ela não cobre.**
> A assinatura é feita **sobre os bytes do `.db`**, não sobre o JSON do `.sig`.
> Portanto os campos do `payload` (CNPJ, vendedor, timestamp, versão) **não são
> protegidos** e podem ser editados sem invalidar nada. Para decisão de negócio,
> use sempre os dados de dentro do `.db` — as tabelas `Empresa` e `Vendedor`,
> que estão cobertas pela assinatura. Trate o `payload` como cabeçalho
> informativo.
>
> A consequência prática está na seção 7.3: recalcular o `hash_db` depois de
> alterar o `.db` faz a conferência de hash passar, mas **não** engana a
> verificação RSA. Por isso a verificação RSA nunca pode ser pulada.

---

## 4. Chave pública

RSA-2048. Fixa para todo o app — **não muda por cliente, por licença ou por
aparelho**. Embuta uma vez no ERP.

```
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzWvISBG0DElIbeXn5GoB
NXGBz0NHBde4eLm87Rf3rtc82cR8P7j/P4lVce2FGTL2HmL3ZV8WZ7YdXW3CZ9YF
5mwMZnfgZxZNbcfYM7rGyoBh8ejyGhTJU3xvBuqSY0zM2DLXBYeL81isefGIQUKw
u/JKmTtJlntjzuyyU0iPyGwuC9Txz6w688Z3xAWoYMyhHMxz2PoOco937D7BEkDO
2yuq7aRvNXB4fT1s17kfSEhftOQl5LtSrDesyZMhAmSAbjWARhD+afumzFxPoHGI
GcD2U7DIQi3Kkkly4BPwYW+7C5quNkqottp7Fxvln2rd4+5240U2vHtg7HqMOFeu
PQIDAQAB
-----END PUBLIC KEY-----
```

O VB6 **não consegue usar o PEM diretamente** — o CryptoAPI exige a chave no
formato `PUBLICKEYBLOB` do Windows. A conversão já está feita: o blob (276
bytes, em hex) está embutido no código da seção 6, na função `ChavePublicaHex`.
Não é preciso converter nada.

---

## 5. Os três detalhes que quebram a implementação

Foram confirmados em teste. Errar qualquer um deles faz a verificação falhar
mesmo com arquivo íntegro:

**1. O provider precisa ser `PROV_RSA_AES` (24), não `PROV_RSA_FULL` (1).**
O provider clássico não conhece SHA-256 — `CryptCreateHash` falha com
`NTE_BAD_ALGID` (`&H80090008`).

**2. A assinatura precisa ser INVERTIDA antes de `CryptVerifySignature`.**
O CryptoAPI trabalha com a assinatura em little-endian; o padrão PKCS#1 (o que
o app gera) é big-endian. Sem inverter os 256 bytes, a verificação falha com
`NTE_BAD_SIGNATURE` (`&H80090006`) mesmo com o arquivo correto. Este é o erro
mais comum e o mais difícil de diagnosticar, porque a mensagem é idêntica à de
um arquivo realmente adulterado.

**3. O hash é dos bytes crus do arquivo.** Ler o `.db` como texto, em modo
ANSI, ou com qualquer conversão de encoding corrompe o hash. Abrir sempre em
modo binário.

---

## 6. Código VB6 completo

Crie um módulo `.bas` (ex.: `modValidaContagem.bas`) e cole o conteúdo abaixo.
Não depende de nenhuma DLL externa nem de componente registrado — só de
`advapi32.dll` e `crypt32.dll`, presentes em qualquer Windows.

```vb
Option Explicit

' ============================================================================
'  Validação da assinatura do arquivo .db de contagens do LogScan (CSCollect)
'  Algoritmo: RSA-2048 / PKCS#1 v1.5 / SHA-256
'  Requer: Windows XP SP3 ou superior (PROV_RSA_AES)
' ============================================================================

Private Declare Function CryptAcquireContext Lib "advapi32.dll" _
    Alias "CryptAcquireContextA" (ByRef phProv As Long, ByVal pszContainer As Long, _
    ByVal pszProvider As Long, ByVal dwProvType As Long, ByVal dwFlags As Long) As Long

Private Declare Function CryptImportKey Lib "advapi32.dll" ( _
    ByVal hProv As Long, ByRef pbData As Byte, ByVal dwDataLen As Long, _
    ByVal hPubKey As Long, ByVal dwFlags As Long, ByRef phKey As Long) As Long

Private Declare Function CryptCreateHash Lib "advapi32.dll" ( _
    ByVal hProv As Long, ByVal Algid As Long, ByVal hKey As Long, _
    ByVal dwFlags As Long, ByRef phHash As Long) As Long

Private Declare Function CryptHashData Lib "advapi32.dll" ( _
    ByVal hHash As Long, ByRef pbData As Byte, ByVal dwDataLen As Long, _
    ByVal dwFlags As Long) As Long

Private Declare Function CryptGetHashParam Lib "advapi32.dll" ( _
    ByVal hHash As Long, ByVal dwParam As Long, ByRef pbData As Byte, _
    ByRef pdwDataLen As Long, ByVal dwFlags As Long) As Long

Private Declare Function CryptVerifySignature Lib "advapi32.dll" _
    Alias "CryptVerifySignatureA" (ByVal hHash As Long, ByRef pbSignature As Byte, _
    ByVal dwSigLen As Long, ByVal hPubKey As Long, ByVal sDescription As Long, _
    ByVal dwFlags As Long) As Long

Private Declare Function CryptDestroyHash Lib "advapi32.dll" (ByVal hHash As Long) As Long
Private Declare Function CryptDestroyKey Lib "advapi32.dll" (ByVal hKey As Long) As Long
Private Declare Function CryptReleaseContext Lib "advapi32.dll" ( _
    ByVal hProv As Long, ByVal dwFlags As Long) As Long

Private Declare Function CryptStringToBinary Lib "crypt32.dll" _
    Alias "CryptStringToBinaryA" (ByVal pszString As String, ByVal cchString As Long, _
    ByVal dwFlags As Long, ByRef pbBinary As Any, ByRef pcbBinary As Long, _
    ByVal pdwSkip As Long, ByVal pdwFlags As Long) As Long

Private Const PROV_RSA_AES        As Long = 24
Private Const CRYPT_VERIFYCONTEXT As Long = &HF0000000   ' negativo no VB6; bits corretos
Private Const CALG_SHA_256        As Long = &H800C
Private Const HP_HASHVAL          As Long = 2
Private Const CRYPT_STRING_BASE64 As Long = 1

' ---------------------------------------------------------------------------
'  FUNÇÃO PRINCIPAL — chame esta antes de importar o .db
'
'  Retorna True somente se o .db for genuíno e não tiver sido alterado.
'  sMensagem recebe o motivo em caso de falha (para log / aviso ao operador).
' ---------------------------------------------------------------------------
Public Function ValidarAssinaturaContagem(ByVal sCaminhoDb As String, _
                                          ByVal sCaminhoSig As String, _
                                          ByRef sMensagem As String) As Boolean
    Dim sJson As String, sSigB64 As String, sHashEsperado As String
    Dim abSig() As Byte, abBlob() As Byte
    Dim hProv As Long, hKey As Long, hHash As Long
    Dim sHashCalc As String

    ValidarAssinaturaContagem = False

    If Dir$(sCaminhoDb) = "" Then
        sMensagem = "Arquivo .db nao encontrado."
        Exit Function
    End If
    If Dir$(sCaminhoSig) = "" Then
        sMensagem = "Arquivo .sig nao encontrado no ZIP. Exportacao incompleta " & _
                    "ou gerada por versao antiga do aplicativo."
        Exit Function
    End If

    ' --- 1. Ler o .sig e extrair os dois campos que interessam ---------------
    sJson = LerArquivoTexto(sCaminhoSig)
    sSigB64 = ExtrairCampoJson(sJson, "assinatura_rsa")
    sHashEsperado = ExtrairCampoJson(sJson, "hash_db")

    If Len(sSigB64) = 0 Then
        sMensagem = "Campo 'assinatura_rsa' nao encontrado no .sig."
        Exit Function
    End If
    If Len(sHashEsperado) = 0 Then
        sMensagem = "Campo 'hash_db' nao encontrado no .sig."
        Exit Function
    End If

    ' --- 2. Base64 -> bytes (256 bytes de assinatura RSA-2048) --------------
    If Not Base64ParaBytes(sSigB64, abSig) Then
        sMensagem = "Assinatura em Base64 invalida no .sig."
        Exit Function
    End If
    If (UBound(abSig) - LBound(abSig) + 1) <> 256 Then
        sMensagem = "Tamanho de assinatura inesperado (esperado 256 bytes)."
        Exit Function
    End If

    ' --- 3. Abrir provider e importar a chave publica -----------------------
    If CryptAcquireContext(hProv, 0, 0, PROV_RSA_AES, CRYPT_VERIFYCONTEXT) = 0 Then
        sMensagem = "Falha ao abrir o provedor de criptografia (erro " & Err.LastDllError & ")."
        GoTo Limpar
    End If

    abBlob = HexParaBytes(ChavePublicaHex())
    If CryptImportKey(hProv, abBlob(0), UBound(abBlob) + 1, 0, 0, hKey) = 0 Then
        sMensagem = "Falha ao importar a chave publica (erro " & Err.LastDllError & ")."
        GoTo Limpar
    End If

    ' --- 4. Calcular SHA-256 do .db (lendo em blocos) -----------------------
    If CryptCreateHash(hProv, CALG_SHA_256, 0, 0, hHash) = 0 Then
        sMensagem = "Falha ao criar o hash SHA-256 (erro " & Err.LastDllError & ")." & _
                    " Verifique se o Windows suporta PROV_RSA_AES."
        GoTo Limpar
    End If

    If Not HashArquivoEmBlocos(hHash, sCaminhoDb) Then
        sMensagem = "Falha ao ler o arquivo .db para calculo do hash."
        GoTo Limpar
    End If

    ' --- 5. Conferir o hash com o declarado no .sig (mensagem mais clara) ---
    sHashCalc = ObterHashHex(hHash)
    If StrComp(sHashCalc, sHashEsperado, vbTextCompare) <> 0 Then
        sMensagem = "O arquivo .db NAO corresponde ao .sig (hash divergente). " & _
                    "O arquivo foi alterado ou esta corrompido."
        GoTo Limpar
    End If

    ' --- 6. Verificar a assinatura RSA --------------------------------------
    '     ATENCAO: o CryptoAPI espera a assinatura em ordem INVERTIDA.
    InverterBytes abSig

    If CryptVerifySignature(hHash, abSig(0), UBound(abSig) + 1, hKey, 0, 0) = 0 Then
        sMensagem = "Assinatura digital invalida. O arquivo .db foi alterado " & _
                    "apos a exportacao e NAO deve ser importado."
        GoTo Limpar
    End If

    sMensagem = "Assinatura valida."
    ValidarAssinaturaContagem = True

Limpar:
    If hHash <> 0 Then CryptDestroyHash hHash
    If hKey <> 0 Then CryptDestroyKey hKey
    If hProv <> 0 Then CryptReleaseContext hProv, 0
End Function

' ---------------------------------------------------------------------------
'  Auxiliares
' ---------------------------------------------------------------------------

Private Function HashArquivoEmBlocos(ByVal hHash As Long, ByVal sCaminho As String) As Boolean
    Dim iFile As Integer, lTam As Long, lLidos As Long, lBloco As Long
    Dim abBuf() As Byte
    Const BLOCO As Long = 32768

    On Error GoTo Falha
    iFile = FreeFile
    Open sCaminho For Binary Access Read As #iFile
    lTam = LOF(iFile)

    If lTam = 0 Then
        Close #iFile
        HashArquivoEmBlocos = False
        Exit Function
    End If

    Do While lLidos < lTam
        lBloco = BLOCO
        If lLidos + lBloco > lTam Then lBloco = lTam - lLidos
        ReDim abBuf(0 To lBloco - 1)
        Get #iFile, lLidos + 1, abBuf
        If CryptHashData(hHash, abBuf(0), lBloco, 0) = 0 Then
            Close #iFile
            HashArquivoEmBlocos = False
            Exit Function
        End If
        lLidos = lLidos + lBloco
    Loop

    Close #iFile
    HashArquivoEmBlocos = True
    Exit Function
Falha:
    On Error Resume Next
    Close #iFile
    HashArquivoEmBlocos = False
End Function

Private Function ObterHashHex(ByVal hHash As Long) As String
    Dim abHash(0 To 31) As Byte, lLen As Long, i As Long, s As String
    lLen = 32
    If CryptGetHashParam(hHash, HP_HASHVAL, abHash(0), lLen, 0) = 0 Then Exit Function
    For i = 0 To 31
        s = s & Right$("0" & Hex$(abHash(i)), 2)
    Next i
    ObterHashHex = LCase$(s)
End Function

Private Function LerArquivoTexto(ByVal sCaminho As String) As String
    Dim iFile As Integer, abBuf() As Byte, lTam As Long
    On Error GoTo Falha
    iFile = FreeFile
    Open sCaminho For Binary Access Read As #iFile
    lTam = LOF(iFile)
    If lTam > 0 Then
        ReDim abBuf(0 To lTam - 1)
        Get #iFile, 1, abBuf
        LerArquivoTexto = StrConv(abBuf, vbUnicode)
    End If
    Close #iFile
    Exit Function
Falha:
    On Error Resume Next
    Close #iFile
    LerArquivoTexto = ""
End Function

' Extrai o valor string de "chave": "valor" do JSON do .sig.
' Simples de proposito: o .sig e gerado sempre no mesmo formato, sem
' caracteres de escape nos campos que o ERP le (Base64 e hex).
Private Function ExtrairCampoJson(ByVal sJson As String, ByVal sChave As String) As String
    Dim p As Long, ini As Long, fim As Long
    p = InStr(1, sJson, """" & sChave & """", vbBinaryCompare)
    If p = 0 Then Exit Function
    p = InStr(p + Len(sChave) + 2, sJson, ":", vbBinaryCompare)
    If p = 0 Then Exit Function
    ini = InStr(p + 1, sJson, """", vbBinaryCompare)
    If ini = 0 Then Exit Function
    fim = InStr(ini + 1, sJson, """", vbBinaryCompare)
    If fim = 0 Then Exit Function
    ExtrairCampoJson = Mid$(sJson, ini + 1, fim - ini - 1)
End Function

Private Function Base64ParaBytes(ByVal sB64 As String, ByRef abOut() As Byte) As Boolean
    Dim lTam As Long
    If CryptStringToBinary(sB64, Len(sB64), CRYPT_STRING_BASE64, ByVal 0&, lTam, 0, 0) = 0 Then Exit Function
    If lTam = 0 Then Exit Function
    ReDim abOut(0 To lTam - 1)
    If CryptStringToBinary(sB64, Len(sB64), CRYPT_STRING_BASE64, abOut(0), lTam, 0, 0) = 0 Then Exit Function
    Base64ParaBytes = True
End Function

Private Function HexParaBytes(ByVal sHex As String) As Byte()
    Dim i As Long, n As Long
    Dim ab() As Byte
    n = Len(sHex) \ 2
    ReDim ab(0 To n - 1)
    For i = 0 To n - 1
        ab(i) = CByte("&H" & Mid$(sHex, i * 2 + 1, 2))
    Next i
    HexParaBytes = ab
End Function

Private Sub InverterBytes(ByRef ab() As Byte)
    Dim i As Long, j As Long, t As Byte
    i = LBound(ab): j = UBound(ab)
    Do While i < j
        t = ab(i): ab(i) = ab(j): ab(j) = t
        i = i + 1: j = j - 1
    Loop
End Sub

' Chave publica RSA-2048 do LogScan em formato PUBLICKEYBLOB (276 bytes, hex).
' Corresponde ao PEM documentado na secao 4. Fixa — nao muda por cliente.
Private Function ChavePublicaHex() As String
    Dim s As String
    s = s & "0602000000A400005253413100080000010001003DAE57388C7AEC607BBC3645"
    s = s & "E376EEE3DD6A9FE51B177BDAB6A84A36AE9A0BBB6F61F013E0724992CA2D42C8"
    s = s & "B053F6C0198871A04F5CCCA6FB69FE104680356E8064022193C9AC37AC52BBE4"
    s = s & "25E4B45F48481FB9D76C3D7D7870356FA4EDAA2BDBCE4012C13EEC778F720EFA"
    s = s & "D873CC1CA1CC60A805C477C6F33AACCFF1D40B2E6CC88F4853B2ECCE637B9649"
    s = s & "3B994AF2BBB0424188F179AC58F38B8705D732D8CC4C6392EA066F7C53C9141A"
    s = s & "F2E8F16180CAC6BA33D8C76D4D1667E077660C6CE605D667C26D5D1DB667165F"
    s = s & "65F7621EF6321985ED7155893FFFB83F7CC4D93CD7AEF717EDBCB978B8D70547"
    s = s & "43CF817135016AE4E7E56D48490CB41148C86BCD"
    ChavePublicaHex = s
End Function
```

### Como usar

```vb
Dim sMsg As String

If ValidarAssinaturaContagem("C:\temp\CONTAGEM_1_043.db", _
                             "C:\temp\CONTAGEM_1_043.sig", sMsg) Then
    ' Assinatura conferida — pode importar o .db com segurança
    Call ImportarContagem("C:\temp\CONTAGEM_1_043.db")
Else
    MsgBox "Importacao cancelada." & vbCrLf & vbCrLf & sMsg, vbCritical, "Arquivo invalido"
End If
```

---

## 7. Exemplo prático — um arquivo válido e um adulterado

Os dois ZIPs abaixo estão em
`CSCollectManager\Contagens\Documentação\` e servem de caso de teste para o
ERP: o primeiro é uma exportação íntegra, o segundo é uma exportação real cuja
coluna `qtdecontada` foi alterada por SQL **depois** de o ZIP ser gerado. Rode
a rotina de validação nos dois: ela tem de aceitar o primeiro e recusar o
segundo.

| | ZIP |
|---|---|
| Válido | `CONTAGEM_1_014_04671382000136_040920261100.zip` |
| Adulterado | `CONTAGEM_1_014_04671382000136_040920261100A.zip` |

O nome segue o padrão `MODELO_empresa_usuário_CNPJ_ddmmaaaahhmm`.

### 7.1 Caso válido — deve importar

Conteúdo do `.db` (`SELECT codean, codproduto, descricaoproduto, unidade,
qtdecontada FROM Produtos`):

```
7622210857293  060459  COOLER PARA PROCESSADOR CPM20 EXBOM      C    12.0
7896089088403  060460  PLACA MAE H61 K LGA1155 REVENGER         1     5.0
7896089088403  060460  PLACA MAE H61 K LGA1155 REVENGER         1     2.0
SEM GTIN       061209  JOGO JUNTA MOTOR CG 160 TITAN START      JG    1.0
SEM GTIN       061362  CHOPE ROMA PILSEN - BARRIL GAVIOLI 30L   VAS   2.0
```

(o `codean 7896089088403` aparece duas vezes porque controla lote — ver §8)

Verificação:

```
Arquivo .db ....... CONTAGEM_1_014_04671382000136_020920261500.db (16.384 bytes)
SHA-256 calculado . 3c6d6a750f421abf5449e0fc983d7dde85e25ac4c2438df366710d30fc26f2ad
payload.hash_db ... 3c6d6a750f421abf5449e0fc983d7dde85e25ac4c2438df366710d30fc26f2ad
Hashes conferem ... SIM
Assinatura RSA .... GuIQkv0CSpEE1KWjGVFDRKWcSn+KOp+BH6Je52uMflOo... (256 bytes)
CryptVerifySignature ... OK

RESULTADO: assinatura válida — pode importar
```

Cabeçalho lido do `.sig` (útil para o log do ERP):

```
cnpj          = 04671382000136
codempresa    = 1
codvendedor   = 014
idcelular     = 97fe33f6f301aa86
timestamp     = 2026-09-02T15:00:11
versao        = 26.09.02 rev. 2
nome_arquivo  = CONTAGEM_1_014_04671382000136_040920261100.zip
```

### 7.2 Caso adulterado — deve ser recusado

Este ZIP foi exportado normalmente às 17:10. Depois, com o `.db` já dentro do
ZIP, rodou-se um `UPDATE` na tabela `Produtos` alterando `qtdecontada`.

O flagrante está no próprio ZIP: o `.pdf`, gerado no momento da exportação,
ainda mostra as quantidades originais, enquanto o `.db` mostra as alteradas.

| Produto | PDF (original) | `.db` depois do SQL |
|---|---|---|
| 060459 — COOLER PARA PROCESSADOR CPM20 EXBOM | 1.000 | **2.0** |
| 060460 — PLACA MAE H61 K LGA1155 REVENGER | 1.000 | **2.0** |

Verificação:

```
Arquivo .db ....... CONTAGEM_1_014_04671382000136_020920261710.db (16.384 bytes)
SHA-256 calculado . 147d86b4fcae684b06ac3a530dd030be8f30f35d15025f04b18aa23b6a55d576
payload.hash_db ... d099cc736a98c6d90554e0403988013dc89ac88354af2f805d784a27cd0b6216
Hashes conferem ... NÃO
Assinatura RSA .... uK6wjvEcuIZzo1QkrDynzt+W/bkj2oxuVJ/nkSykTNp5... (256 bytes)
CryptVerifySignature ... FALHA (NTE_BAD_SIGNATURE, &H80090006)

RESULTADO: assinatura inválida — NÃO importar
```

Repare que o hash divergiu já no primeiro caractere. Isso é esperado: SHA-256
não muda "um pedacinho" quando o arquivo muda um pedacinho — muda inteiro.

Conferindo os três arquivos do ZIP contra os hashes do `.sig`, dá para apontar
exatamente **o que** foi mexido:

| Arquivo | Hash confere? |
|---|---|
| `.db` | **NÃO** ← foi este |
| `.pdf` | sim |
| `_metricas.enc` | sim |

O `.pdf` intacto é a prova documental: ele foi assinado junto e continua
dizendo 1.000 onde o banco passou a dizer 2.0.

### 7.3 Por que não basta conferir o hash

Um fraudador mais atento alteraria o `.db` **e** recalcularia o `hash_db`
dentro do `.sig` — afinal o `.sig` é texto e o SHA-256 é público. Nesse caso a
conferência de hash passa:

```
UPDATE Produtos SET qtdecontada = 999;      -- altera o .db
hash_db no .sig reescrito com o novo SHA-256

Hashes conferem ....... SIM   (o fraudador ajustou)
CryptVerifySignature .. FALHA (a assinatura barrou)
```

Refazer a `assinatura_rsa` exigiria a chave **privada**, que só existe dentro
do LogScan e nunca é distribuída. É por isso que a conferência de hash é
apenas um diagnóstico (dá uma mensagem melhor ao operador) e a verificação RSA
é a trava de verdade.

**Consequência para o ERP: nunca importe apenas porque o hash bateu.** As duas
conferências têm de passar, e a que decide é a RSA.

### 7.4 O tamanho do arquivo não muda

Nos dois ZIPs o `.db` tem exatamente 16.384 bytes. Conferir tamanho, data de
modificação ou contagem de registros não detecta nada. Alterando uma única
quantidade no arquivo válido:

```
Antes  ... 3c6d6a750f421abf5449e0fc983d7dde85e25ac4c2438df366710d30fc26f2ad
Depois ... 63fb525f53afd5e71098230a6a5a667f2bc66a9450b5fda9a625494ab51f8c08
Tamanho ... 16.384 bytes nos dois casos (98 bytes internos diferentes)
```

O SQLite reescreve a página inteira e o cabeçalho de versão, mas o arquivo
continua do mesmo tamanho. Só a assinatura acusa.

### 7.5 Roteiro de teste no ERP

1. Extrair o ZIP válido e chamar `ValidarAssinaturaContagem` com o `.db` e o
   `.sig`. Deve retornar `True` e `"Assinatura valida."`.
2. Extrair o ZIP adulterado e repetir. Deve retornar `False` com a mensagem de
   hash divergente.
3. Pegar o `.db` válido, abrir no DB Browser for SQLite, mudar qualquer
   `qtdecontada`, salvar e validar de novo — deve recusar.
4. Só depois de passar nos três, ligar a importação de verdade.

---

## 8. Schema do `.db` (para a importação)

SQLite, 3 tabelas, cada uma com uma coluna `tipo` fixa:

```sql
CREATE TABLE Empresa  (tipo TEXT, codempresa INTEGER, local TEXT, cnpj TEXT);
-- 1 linha, tipo = 'E'

CREATE TABLE Vendedor (tipo TEXT, codusuario INTEGER);
-- 1 linha, tipo = 'V'

CREATE TABLE Produtos (
    tipo TEXT, codean TEXT, codproduto TEXT, descricaoproduto TEXT, unidade TEXT,
    qtdecontada REAL, controlalote INTEGER, numlote TEXT, datafab TEXT, dataval TEXT,
    codgrupo TEXT, nomegrupo TEXT, localizacao TEXT
);
-- tipo = 'P'
-- produto sem lote  -> 1 linha (controlalote = 0; numlote/datafab/dataval nulos)
-- produto com lote  -> 1 linha por lote contado (controlalote = 1)
```

Um mesmo `codean` aparece em várias linhas quando `controlalote = 1`.

**Formato das datas:** `datafab` e `dataval` vêm sempre como **DDMMAAAA**,
8 dígitos sem separador (`17082026`) — o mesmo formato em que a carga entrega
essas datas ao aplicativo. Vale tanto para o lote que veio da carga quanto para
o incluído pelo conferente durante a contagem. Em produto sem controle de lote
os dois campos vêm nulos.

> Versões anteriores a 26.09.04 gravavam o lote **incluído na contagem** como
> `01/01/2026`, com barras, enquanto o lote vindo da carga saía como
> `17082026` — duas grafias na mesma coluna, e a segunda quebrava a
> importação. Corrigido: a exportação agora normaliza os dois casos para
> DDMMAAAA, inclusive lotes que já estavam gravados com barras no aparelho.

---

## 9. Tabela de decisão

| Situação | Ação do ERP |
|---|---|
| `.sig` ausente no ZIP | Rejeitar — exportação incompleta ou app muito antigo |
| Hash do `.db` ≠ `payload.hash_db` | Rejeitar — arquivo alterado ou corrompido (§7.2) |
| Hash confere, mas assinatura RSA falha | Rejeitar — adulteração com `.sig` remontado (§7.3) |
| Assinatura RSA não confere | Rejeitar — arquivo alterado após a exportação |
| Hash e RSA conferem | Importar normalmente |

**Nunca importe um `.db` cuja assinatura RSA não passou.** É exatamente o
cenário que essa assinatura existe para impedir: alguém abrir o SQLite,
alterar uma quantidade contada e reimportar.

---

## 10. Diagnóstico de erros

| Sintoma | Causa provável |
|---|---|
| `CryptCreateHash` falha, erro `&H80090008` (NTE_BAD_ALGID) | Usou `PROV_RSA_FULL` (1) em vez de `PROV_RSA_AES` (24) |
| Assinatura sempre inválida, mesmo com arquivo original | Esqueceu de inverter os bytes da assinatura (seção 5, item 2) |
| `CryptImportKey` falha | Blob da chave truncado — confira se `ChavePublicaHex` tem 552 caracteres |
| Hash sempre divergente | `.db` sendo lido em modo texto em vez de binário |
| `CryptAcquireContext` falha | Faltou a flag `CRYPT_VERIFYCONTEXT` |

Para separar "erro meu" de "arquivo realmente adulterado", use os dois ZIPs da
seção 7: se o **válido** (§7.1) também é recusado, o problema é a
implementação — quase sempre a inversão de bytes. Se o válido passa e só o
adulterado (§7.2) é recusado, está funcionando como deveria.

---

## 11. Referências

- Geração da assinatura: `security/export_db_signing.py` (repositório CSCollect)
- Montagem do ZIP: `screens/exportar.py`
- Arquivos de exemplo da seção 7:
  `CONTAGEM_1_014_04671382000136_040920261100.zip`
  (válido) e `..._040920261100A.zip` (adulterado)
- Chave pública em PEM: `CSCollectAPI/docs/export_db_public_key.pem`
- Validação feita pela CSCollectAPI (campo HMAC, não usado pelo ERP):
  `CSCollectAPI/docs/VALIDACAO_ASSINATURA_SIG.md`
