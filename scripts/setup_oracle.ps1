param(
    [string]$OracleHome = 'C:\oracle19c',
    [string]$OracleSid = 'orcl',
    [string]$PdbName = 'ORCLPDB'
)
$ErrorActionPreference = 'Stop'
if ($PdbName -and ($PdbName.Length -gt 128 -or $PdbName -notmatch '^[a-zA-Z][a-zA-Z0-9_#$]*$')) { throw 'Nom de PDB invalide.' }
$projectDir = Split-Path $PSScriptRoot -Parent
$sqlplus = Join-Path $OracleHome 'bin\sqlplus.exe'
if (-not (Test-Path -LiteralPath $sqlplus)) { throw "SQLPlus absent dans $OracleHome." }
$env:ORACLE_HOME = $OracleHome
$env:ORACLE_SID = $OracleSid
$oracleService = Get-Service -Name ('OracleService' + $OracleSid) -ErrorAction SilentlyContinue
if (-not $oracleService) { throw "Service OracleService$OracleSid introuvable. Vérifier le SID de l'installation." }
if ($oracleService.Status -ne 'Running') { Start-Service -Name $oracleService.Name }
$listener = Get-Service -Name '*Oracle*TNSListener*' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener -and $listener.Status -ne 'Running') { Start-Service -Name $listener.Name }

$workDir = Join-Path $projectDir 'work'
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
$probePath = Join-Path $workDir 'oracle_preflight.sql'
@'
whenever oserror exit failure
whenever sqlerror exit failure
set echo off feedback off heading off verify off pagesize 0
select 'Connexion administrative locale réussie' from dual;
declare
  n number;
begin
  select count(*) into n from dba_users where username='BIBLIOTHEQUE';
  if n > 0 then
    raise_application_error(-20001,'Le compte BIBLIOTHEQUE existe déjà dans ce conteneur. Aucun mot de passe réinitialisé.');
  end if;
end;
/
exit success
'@ | Set-Content -LiteralPath $probePath -Encoding ascii
& $sqlplus -L '/ as sysdba' ('@' + $probePath)
if ($LASTEXITCODE -ne 0) { throw 'Connexion administrative refusée ou compte déjà présent. Aucun compte modifié. Lancer avec un compte Windows membre du groupe Oracle ORA_DBA ; les droits administrateur Windows seuls ne garantissent pas cet accès.' }

# Générer un mot de passe aléatoire sans le montrer ou le transmettre en argument.
$bytes = New-Object byte[] 12
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$rng.Dispose()
$projectPassword = 'Bi9_' + ([BitConverter]::ToString($bytes).Replace('-', ''))
$serviceFile = Join-Path $workDir 'oracle_service.txt'
$setupPath = Join-Path $workDir 'oracle_create_project.sql'
$template = @'
whenever oserror exit failure
whenever sqlerror exit failure
set echo off feedback off heading off verify off pagesize 0 serveroutput on
set define off
prompt PDB disponibles et etats actuels :
select name || ' : ' || open_mode from v$pdbs where name<>'PDB$SEED' order by name;
variable chosen_pdb varchar2(128)
declare
  is_cdb varchar2(3);
  pdb_count number;
  chosen_name varchar2(128);
  chosen_mode varchar2(20);
  requested_name varchar2(128) := upper('__PDB_NAME__');
begin
  select cdb into is_cdb from v$database;
  if is_cdb='YES' then
    if requested_name is not null then
      select count(*) into pdb_count from v$pdbs where name=requested_name and name<>'PDB$SEED';
      if pdb_count<>1 then
        raise_application_error(-20002,'PDB demandee introuvable. Utiliser un nom affiche ci-dessus.');
      end if;
      chosen_name := requested_name;
    else
      select count(*) into pdb_count from v$pdbs where name<>'PDB$SEED';
      if pdb_count=1 then
        select name into chosen_name from v$pdbs where name<>'PDB$SEED';
      else
        select count(*) into pdb_count from v$pdbs where name<>'PDB$SEED' and open_mode='READ WRITE';
        if pdb_count=1 then
          select name into chosen_name from v$pdbs where name<>'PDB$SEED' and open_mode='READ WRITE';
        else
          raise_application_error(-20002,'PDB ambigues ou absentes. Relancer avec -PdbName NOM parmi les PDB affichees.');
        end if;
      end if;
    end if;
    select open_mode into chosen_mode from v$pdbs where name=chosen_name;
    if chosen_mode='MOUNTED' then
      execute immediate 'alter pluggable database ' || dbms_assert.enquote_name(chosen_name,false) || ' open read write';
    elsif chosen_mode<>'READ WRITE' then
      raise_application_error(-20005,'La PDB choisie est en lecture seule. Aucun changement de mode force.');
    end if;
    :chosen_pdb := chosen_name;
    dbms_output.put_line('PDB selectionnee : ' || chosen_name);
  end if;
end;
/
alter system register;
alter session set container="__PDB_NAME__";
declare
  n number;
  permanent_ts varchar2(128);
  temporary_ts varchar2(128);
begin
  if upper(sys_context('USERENV','CON_NAME'))<>upper('__PDB_NAME__') then
    raise_application_error(-20006,'Conteneur incorrect : aucun compte cree.');
  end if;
  dbms_output.put_line('Conteneur confirme : ' || sys_context('USERENV','CON_NAME'));
  select count(*) into n from dba_users where username='BIBLIOTHEQUE';
  if n>0 then
    raise_application_error(-20003,'BIBLIOTHEQUE existe déjà. Aucun mot de passe modifié.');
  end if;
  select property_value into permanent_ts from database_properties where property_name='DEFAULT_PERMANENT_TABLESPACE';
  select property_value into temporary_ts from database_properties where property_name='DEFAULT_TEMP_TABLESPACE';
  if permanent_ts in ('SYSTEM','SYSAUX') then
    raise_application_error(-20004,'Configurer un tablespace utilisateur par défaut avant de créer le compte.');
  end if;
  execute immediate 'create user BIBLIOTHEQUE identified by "__PASSWORD__" default tablespace '
    || dbms_assert.enquote_name(permanent_ts,false) || ' temporary tablespace '
    || dbms_assert.enquote_name(temporary_ts,false) || ' quota 500M on '
    || dbms_assert.enquote_name(permanent_ts,false);
  execute immediate 'grant create session, create table, create sequence to BIBLIOTHEQUE';
end;
/
spool "__SERVICE_FILE__"
select name from v$services
where con_id=to_number(sys_context('USERENV','CON_ID'))
  and upper(name) not like 'SYS%' and upper(name) not like '%XDB%' and rownum=1;
spool off
exit success
'@
$template.Replace('__PASSWORD__',$projectPassword).Replace('__SERVICE_FILE__',$serviceFile).Replace('__PDB_NAME__',$PdbName) | Set-Content -LiteralPath $setupPath -Encoding ascii
try {
    & $sqlplus -L '/ as sysdba' ('@' + $setupPath)
    if ($LASTEXITCODE -ne 0) { throw 'Création du compte interrompue. Les DDL Oracle ne sont pas annulables ; vérifier BIBLIOTHEQUE avant de relancer. Les comptes existants restent inchangés.' }
    $serviceName = (Get-Content -LiteralPath $serviceFile | Where-Object { $_.Trim() } | Select-Object -First 1).Trim()
    if (-not $serviceName -or $serviceName -notmatch '^[a-zA-Z0-9_.-]+$') { throw 'Compte créé, mais service réseau non identifié. Le mot de passe est conservé dans work\oracle_create_project.sql pour récupération locale.' }
    $configPath = Join-Path $projectDir '.env'
    $configText = if (Test-Path -LiteralPath $configPath) { Get-Content -LiteralPath $configPath -Raw } else { Get-Content -LiteralPath (Join-Path $projectDir '.env.example') -Raw }
    $configValues = @{ DB_BACKEND='oracle'; ORACLE_USER='BIBLIOTHEQUE'; ORACLE_PASSWORD=$projectPassword; ORACLE_DSN=('localhost:1521/' + $serviceName) }
    foreach ($key in $configValues.Keys) {
        $line = $key + '=' + $configValues[$key]
        if ($configText -match ('(?m)^' + $key + '=')) { $configText = [regex]::Replace($configText,('(?m)^' + $key + '=.*$'),$line) }
        else { $configText += "`n$line" }
    }
    Set-Content -LiteralPath $configPath -Value $configText -Encoding utf8
    # Effacer le secret du script SQL après sauvegarde réussie dans .env.
    Set-Content -LiteralPath $setupPath -Value '-- Configuration terminée. Le secret est dans .env local.' -Encoding ascii
    Write-Host ('Compte BIBLIOTHEQUE créé. Service : ' + $serviceName + '. Configuration .env écrite. Aucun mot de passe affiché.')
} finally { $projectPassword = $null }




