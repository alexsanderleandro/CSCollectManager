# Validação de Licença - Referência para APK Android

## 📱 Visão Geral

Este documento descreve como implementar a validação de licença no aplicativo Android (APK) do CSCollectManager, utilizando o novo formato JSON.

### Diferenças entre Desktop e Mobile

| Aspecto | Desktop (Windows) | Mobile (Android) |
|---------|------------------|------------------|
| **CNPJ** | ✅ Validado | ✅ Validado |
| **Validade** | ✅ Validado | ✅ Validado |
| **Device ID** | ❌ Não validado | ✅ **Validado (obrigatório)** |
| **Online DB** | ✅ Opcional | ✅ Opcional |

**⚠️ IMPORTANTE**: No APK, o **ID do celular DEVE ser validado** para garantir que a licença está sendo usada no dispositivo autorizado.

---

## 📄 Formato do Arquivo de Licença

O arquivo `licenca.key` deve estar no formato JSON:

```json
{
    "cnpjs": ["65381113000120", "12345678000190"],
    "ids": ["a3e9e3a0a4659652", "b4f0f4b1b5760763"],
    "token": "eyJjbnBqcyI6WyI2NTM4MTExMzAwMDEyMCJdLCJpZHMiOlsiYTNlOWUzYTBhNDY1OTY1MiJdLCJ2YWxpZGFkZSI6IjIwMjYtMDUtMDEifQ.xYzW1v2u3t4s5r6q7p8o9n0m1l2k3j4i5h6g7f8e9d0c",
    "validade": "2026-05-01",
    "database_url": "postgresql://user:pass@host:5432/db"
}
```

### Campos do Arquivo

| Campo | Tipo | Descrição | Obrigatório |
|-------|------|-----------|-------------|
| `cnpjs` | Array[String] | Lista de CNPJs autorizados | ✅ Sim |
| `ids` | Array[String] | Lista de IDs de dispositivos autorizados | ✅ Sim |
| `token` | String | Token HMAC-SHA256 no formato `payload.signature` | ✅ Sim |
| `validade` | String | Data de expiração (formato ISO: YYYY-MM-DD) | ✅ Sim |
| `database_url` | String | URL PostgreSQL para validação online | ❌ Não |

---

## 🔐 Estrutura do Token

### Formato
```
token = base64url(payload) + "." + base64url(signature)
```

### Payload (JSON antes de codificar)
```json
{
    "cnpjs": ["65381113000120"],
    "ids": ["a3e9e3a0a4659652"],
    "validade": "2026-05-01"
}
```

### Signature
```
signature = HMAC-SHA256(payload_bytes, MASTER_KEY)
```

---

## 🛠️ Implementação Android

### 1. Obter o Device ID (Android)

```kotlin
import android.provider.Settings
import android.content.Context

fun obterDeviceId(context: Context): String {
    return Settings.Secure.getString(
        context.contentResolver,
        Settings.Secure.ANDROID_ID
    )
}
```

**Exemplo de Device ID**: `a3e9e3a0a4659652`

### 2. Carregar o Arquivo de Licença

```kotlin
import org.json.JSONObject
import org.json.JSONArray
import java.io.File

data class Licenca(
    val cnpjs: List<String>,
    val ids: List<String>,
    val token: String,
    val validade: String,
    val databaseUrl: String?
)

fun carregarLicenca(caminhoArquivo: String): Licenca {
    val conteudo = File(caminhoArquivo).readText()
    val json = JSONObject(conteudo)
    
    // Extrair CNPJs
    val cnpjsArray = json.getJSONArray("cnpjs")
    val cnpjs = (0 until cnpjsArray.length()).map { 
        cnpjsArray.getString(it) 
    }
    
    // Extrair IDs
    val idsArray = json.getJSONArray("ids")
    val ids = (0 until idsArray.length()).map { 
        idsArray.getString(it) 
    }
    
    return Licenca(
        cnpjs = cnpjs,
        ids = ids,
        token = json.getString("token"),
        validade = json.getString("validade"),
        databaseUrl = json.optString("database_url", null)
    )
}
```

### 3. Validar o Token HMAC-SHA256

```kotlin
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import android.util.Base64
import java.nio.charset.StandardCharsets

fun validarToken(token: String, masterKey: String): Boolean {
    try {
        // Separar payload e signature
        val partes = token.split(".")
        if (partes.size != 2) {
            throw IllegalArgumentException("Formato de token inválido")
        }
        
        val payloadB64 = partes[0]
        val signatureB64Recebida = partes[1]
        
        // Decodificar payload
        val payloadBytes = Base64.decode(
            payloadB64, 
            Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP
        )
        
        // Calcular signature esperada
        val mac = Mac.getInstance("HmacSHA256")
        val secretKey = SecretKeySpec(
            masterKey.toByteArray(StandardCharsets.UTF_8), 
            "HmacSHA256"
        )
        mac.init(secretKey)
        val signatureCalculada = mac.doFinal(payloadBytes)
        
        // Codificar em base64
        val signatureB64Calculada = Base64.encodeToString(
            signatureCalculada,
            Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP
        )
        
        // Comparação segura
        return signatureB64Recebida == signatureB64Calculada
        
    } catch (e: Exception) {
        e.printStackTrace()
        return false
    }
}
```

### 4. Validação Completa Offline

```kotlin
import java.time.LocalDate
import java.time.format.DateTimeFormatter

data class ResultadoValidacao(
    val sucesso: Boolean,
    val mensagem: String,
    val nomeCliente: String? = null
)

fun validarLicencaOffline(
    licenca: Licenca,
    cnpjConfigurado: String,
    deviceId: String,
    masterKey: String
): ResultadoValidacao {
    
    // 1. Validar token HMAC
    if (!validarToken(licenca.token, masterKey)) {
        return ResultadoValidacao(
            sucesso = false,
            mensagem = "Token de licença inválido (assinatura não confere)"
        )
    }
    
    // 2. Validar CNPJ
    if (!licenca.cnpjs.contains(cnpjConfigurado)) {
        return ResultadoValidacao(
            sucesso = false,
            mensagem = "CNPJ $cnpjConfigurado não autorizado nesta licença"
        )
    }
    
    // 3. Validar Device ID (OBRIGATÓRIO NO APK!)
    if (!licenca.ids.contains(deviceId)) {
        return ResultadoValidacao(
            sucesso = false,
            mensagem = "Device ID $deviceId não autorizado nesta licença.\n" +
                      "IDs autorizados: ${licenca.ids.joinToString(", ")}"
        )
    }
    
    // 4. Validar data de validade
    val hoje = LocalDate.now()
    val dataValidade = LocalDate.parse(
        licenca.validade, 
        DateTimeFormatter.ISO_DATE
    )
    
    if (hoje.isAfter(dataValidade)) {
        return ResultadoValidacao(
            sucesso = false,
            mensagem = "Licença expirada em ${licenca.validade}"
        )
    }
    
    // Licença válida!
    return ResultadoValidacao(
        sucesso = true,
        mensagem = "Licença válida até ${licenca.validade}",
        nomeCliente = "Cliente autorizado"
    )
}
```

### 5. Validação Online (PostgreSQL)

```kotlin
import java.sql.DriverManager
import java.sql.Connection

fun validarLicencaOnline(
    licenca: Licenca,
    cnpjConfigurado: String,
    deviceId: String
): ResultadoValidacao {
    
    if (licenca.databaseUrl == null) {
        return ResultadoValidacao(
            sucesso = false,
            mensagem = "URL do banco de dados não configurada"
        )
    }
    
    var connection: Connection? = null
    
    try {
        // Conectar ao PostgreSQL
        Class.forName("org.postgresql.Driver")
        connection = DriverManager.getConnection(licenca.databaseUrl)
        
        // Query de validação
        val sql = """
            SELECT razao_social, ativo, data_expiracao 
            FROM licencas 
            WHERE cnpj = ? AND device_id = ?
        """.trimIndent()
        
        val statement = connection.prepareStatement(sql)
        statement.setString(1, cnpjConfigurado)
        statement.setString(2, deviceId)
        
        val resultSet = statement.executeQuery()
        
        if (!resultSet.next()) {
            return ResultadoValidacao(
                sucesso = false,
                mensagem = "Licença não encontrada no servidor"
            )
        }
        
        val razaoSocial = resultSet.getString("razao_social")
        val ativo = resultSet.getBoolean("ativo")
        val dataExpiracao = resultSet.getDate("data_expiracao")
        val hoje = java.sql.Date(System.currentTimeMillis())
        
        if (!ativo) {
            return ResultadoValidacao(
                sucesso = false,
                mensagem = "Licença desativada no servidor"
            )
        }
        
        if (dataExpiracao != null && hoje.after(dataExpiracao)) {
            return ResultadoValidacao(
                sucesso = false,
                mensagem = "Licença expirada no servidor"
            )
        }
        
        return ResultadoValidacao(
            sucesso = true,
            mensagem = "Licença validada online com sucesso",
            nomeCliente = razaoSocial
        )
        
    } catch (e: Exception) {
        e.printStackTrace()
        return ResultadoValidacao(
            sucesso = false,
            mensagem = "Erro ao validar online: ${e.message}"
        )
    } finally {
        connection?.close()
    }
}
```

### 6. Fluxo Completo de Validação

```kotlin
fun validarLicencaCompleta(
    context: Context,
    caminhoLicenca: String,
    cnpjConfigurado: String,
    masterKey: String,
    validarOnline: Boolean = false
): ResultadoValidacao {
    
    try {
        // 1. Obter Device ID
        val deviceId = obterDeviceId(context)
        
        // 2. Carregar licença
        val licenca = carregarLicenca(caminhoLicenca)
        
        // 3. Validação offline (sempre executada)
        val resultadoOffline = validarLicencaOffline(
            licenca, 
            cnpjConfigurado, 
            deviceId, 
            masterKey
        )
        
        if (!resultadoOffline.sucesso) {
            return resultadoOffline
        }
        
        // 4. Validação online (opcional)
        if (validarOnline && licenca.databaseUrl != null) {
            val resultadoOnline = validarLicencaOnline(
                licenca, 
                cnpjConfigurado, 
                deviceId
            )
            
            if (!resultadoOnline.sucesso) {
                return resultadoOnline
            }
        }
        
        return resultadoOffline
        
    } catch (e: Exception) {
        e.printStackTrace()
        return ResultadoValidacao(
            sucesso = false,
            mensagem = "Erro ao validar licença: ${e.message}"
        )
    }
}
```

---

## 📱 Integração no App Android

### Activity de Login

```kotlin
class LoginActivity : AppCompatActivity() {
    
    private val MASTER_KEY = "SUA_MASTER_KEY_AQUI" // Mínimo 32 caracteres!
    private val CAMINHO_LICENCA = "/data/data/com.seuapp/files/licenca.key"
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_login)
        
        // Validar licença antes de exibir login
        validarLicencaAoIniciar()
    }
    
    private fun validarLicencaAoIniciar() {
        // Obter CNPJ das configurações
        val sharedPrefs = getSharedPreferences("config", Context.MODE_PRIVATE)
        val cnpj = sharedPrefs.getString("cnpj", null)
        
        if (cnpj == null) {
            exibirErro("CNPJ não configurado")
            return
        }
        
        // Validar licença
        val resultado = validarLicencaCompleta(
            context = this,
            caminhoLicenca = CAMINHO_LICENCA,
            cnpjConfigurado = cnpj,
            masterKey = MASTER_KEY,
            validarOnline = false // Alterar para true se quiser validação online
        )
        
        if (!resultado.sucesso) {
            exibirErro(resultado.mensagem)
            finish() // Fecha o app
        } else {
            // Licença válida, prosseguir
            Log.i("Licenca", "Licença válida: ${resultado.mensagem}")
        }
    }
    
    private fun exibirErro(mensagem: String) {
        AlertDialog.Builder(this)
            .setTitle("Erro de Licença")
            .setMessage(mensagem)
            .setPositiveButton("OK") { _, _ -> finish() }
            .setCancelable(false)
            .show()
    }
}
```

---

## 🔑 MASTER_KEY - Segurança

### ⚠️ Importante

A `MASTER_KEY` deve ser:
- **Mínimo 32 caracteres** (256 bits)
- **Mesma chave** usada na geração da licença (Python)
- **Armazenada com segurança** no APK

### Exemplo de Ofuscação

```kotlin
// Não recomendado (muito exposto):
const val MASTER_KEY = "minha_master_key_123"

// Melhor - usar NDK (C/C++) ou obfuscação:
object SecurityConfig {
    external fun getMasterKey(): String
    
    init {
        System.loadLibrary("security")
    }
}
```

### Alternativa - Usar BuildConfig

```gradle
// build.gradle
android {
    defaultConfig {
        buildConfigField "String", "MASTER_KEY", "\"${project.findProperty('MASTER_KEY')}\""
    }
}
```

```kotlin
val masterKey = BuildConfig.MASTER_KEY
```

---

## 📦 Dependências Gradle

```gradle
dependencies {
    // PostgreSQL (se validação online)
    implementation 'org.postgresql:postgresql:42.6.0'
    
    // JSON (já incluído no Android)
    // org.json está disponível nativamente
}
```

### Permissões AndroidManifest.xml

```xml
<!-- Para validação online -->
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

<!-- Para ler ANDROID_ID -->
<uses-permission android:name="android.permission.READ_PHONE_STATE" />
```

---

## 🧪 Testando a Validação

### 1. Gerar Licença de Teste (Python)

```bash
python licenca.py
```

Preencher:
- CNPJs: `65381113000120`
- Device IDs: `a3e9e3a0a4659652` (seu ANDROID_ID)
- Data validade: `2026-12-31`
- Database URL: (deixar vazio para teste offline)

### 2. Copiar para o Android

```bash
adb push licenca.key /data/data/com.seuapp/files/licenca.key
```

### 3. Verificar Device ID do Celular

```kotlin
val deviceId = Settings.Secure.getString(
    contentResolver,
    Settings.Secure.ANDROID_ID
)
Log.d("DeviceID", "Meu Device ID: $deviceId")
```

### 4. Executar Validação

```kotlin
val resultado = validarLicencaCompleta(
    context = this,
    caminhoLicenca = "/data/data/com.seuapp/files/licenca.key",
    cnpjConfigurado = "65381113000120",
    masterKey = "SUA_MASTER_KEY",
    validarOnline = false
)

Log.d("Validacao", "Sucesso: ${resultado.sucesso}")
Log.d("Validacao", "Mensagem: ${resultado.mensagem}")
```

---

## 🆚 Comparação: Desktop vs Mobile

### Desktop (Windows - Python)
```python
# Validação com device ID OPCIONAL
resultado = validar_licenca_completa(
    licenca,
    cnpj_configurado,
    validar_device_id=False  # ❌ Não valida device ID
)
```

### Mobile (Android - Kotlin)
```kotlin
// Validação com device ID OBRIGATÓRIO
val resultado = validarLicencaOffline(
    licenca,
    cnpjConfigurado,
    deviceId  // ✅ SEMPRE valida device ID
)
```

---

## 📋 Checklist de Implementação

- [ ] Implementar `obterDeviceId()` usando ANDROID_ID
- [ ] Implementar `carregarLicenca()` para ler JSON
- [ ] Implementar `validarToken()` com HMAC-SHA256
- [ ] Implementar `validarLicencaOffline()` **COM validação de Device ID**
- [ ] (Opcional) Implementar `validarLicencaOnline()` para PostgreSQL
- [ ] Integrar validação na Activity de Login
- [ ] Adicionar permissões ao AndroidManifest.xml
- [ ] Proteger MASTER_KEY (NDK ou BuildConfig)
- [ ] Testar com licença válida
- [ ] Testar com licença expirada
- [ ] Testar com CNPJ não autorizado
- [ ] Testar com Device ID não autorizado ⚠️
- [ ] Testar sem arquivo de licença
- [ ] Testar validação online (se implementada)

---

## 🚨 Mensagens de Erro Comuns

| Erro | Causa | Solução |
|------|-------|---------|
| `Formato de token inválido` | Token não tem formato `payload.signature` | Verificar geração da licença |
| `Token de licença inválido` | MASTER_KEY diferente ou payload alterado | Usar mesma MASTER_KEY do Python |
| `CNPJ não autorizado` | CNPJ não está na lista `cnpjs` | Adicionar CNPJ na licença |
| `Device ID não autorizado` | ANDROID_ID não está na lista `ids` | ⚠️ Adicionar Device ID na licença |
| `Licença expirada` | Data de validade passou | Gerar nova licença com data futura |
| `Arquivo de licença não encontrado` | Arquivo não está no caminho esperado | Copiar licenca.key para o dispositivo |

---

## 📞 Suporte

Para gerar novas licenças, use o script Python:

```bash
python licenca.py
```

Certifique-se de:
1. Usar a **mesma MASTER_KEY** no Python e no Android
2. Incluir o **ANDROID_ID correto** do celular
3. Incluir o **CNPJ correto** da empresa
4. Definir uma **data de validade futura**

---

## 📄 Licença

CSCollectManager - Sistema de Gestão de Inventário
© 2026 CEOSoftware
