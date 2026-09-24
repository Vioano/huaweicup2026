param([Parameter(Mandatory=$true)][string]$ApprovalPath,
      [Parameter(Mandatory=$true)][string]$EvidenceName)

# Preparation artifact only. This script has NOT been invoked, including --help.
# Reflection.Emit supplies P/Invoke declarations without a compiler/build process.
$e2T0Utc = [DateTimeOffset]::UtcNow.ToString('o')
$e2T0Qpc = [Diagnostics.Stopwatch]::GetTimestamp()
$e2Frequency = [Diagnostics.Stopwatch]::Frequency
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 8) { throw 'Only the pinned Windows x64 layout is proposed' }
$e2Here = [IO.Path]::GetFullPath($PSScriptRoot)
$e2Root = [IO.Path]::GetFullPath((Join-Path $e2Here '../../../..'))
$e2Approval = Get-Content -LiteralPath $ApprovalPath -Raw | ConvertFrom-Json
if ($e2Approval.approved -ne $true -or $e2Approval.execution_enabled -ne $true -or
    $e2Approval.runtime_review_closed -ne $true -or -not $e2Approval.approval_reference) {
    throw 'No approved execution window; driver preparation does not authorize running'
}
$e2Contract = Get-Content -LiteralPath (Join-Path $e2Here 'contract.json') -Raw | ConvertFrom-Json
if ($e2Contract.execution_blockers.Count -ne 0) { throw 'Driver preparation checkpoint still has static execution blockers' }
if ($EvidenceName -notmatch '^[a-z0-9][a-z0-9-]{5,80}$') { throw 'Invalid evidence directory name' }
$e2Manifest = Get-Content -LiteralPath (Join-Path $e2Here 'sources.json') -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath (Join-Path $e2Here 'sources.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne
    $e2Approval.sources_sha256) { throw 'Approval source manifest mismatch' }
foreach ($e2Property in $e2Manifest.driver_files.PSObject.Properties) {
    $e2ActualHash = (Get-FileHash -LiteralPath (Join-Path $e2Here $e2Property.Name) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($e2ActualHash -ne $e2Property.Value) { throw "Driver identity mismatch: $($e2Property.Name)" }
}
if ($e2Approval.driver_bundle_sha256 -ne $e2Manifest.driver_bundle_sha256) { throw 'Approval bundle mismatch' }
$e2Head = (git -C $e2Root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $e2Head -ne $e2Approval.driver_commit) { throw 'Approval HEAD mismatch' }
$e2Dirty = git -C $e2Root status --porcelain
if ($LASTEXITCODE -ne 0 -or $e2Dirty) { throw 'Require clean fixed driver tree' }
$e2PrivateBase = Join-Path $env:LOCALAPPDATA 'CodexEvidence'
$e2Run = Join-Path $e2PrivateBase $EvidenceName
if (Test-Path -LiteralPath $e2Run) { throw 'Evidence path already exists; no retry/overwrite' }
[IO.Directory]::CreateDirectory($e2Run) | Out-Null
[IO.File]::Copy([IO.Path]::GetFullPath($ApprovalPath), (Join-Path $e2Run 'approval.json'), $false)
$e2Outer = [ordered]@{ schema='e2-cli-fixed-driver-v1'; outer_t0_utc=$e2T0Utc;
    outer_t0_qpc=$e2T0Qpc; qpc_frequency=$e2Frequency; driver_commit=$e2Head;
    driver_bundle_sha256=$e2Manifest.driver_bundle_sha256; control_launch_requests=1;
    root_job_active_limit=17; root_job_commit_limit_bytes=2415919104;
    controller_private_budget_bytes=268435456; forced_outer_cleanup=$false;
    status='preparing'; close_errors=@() }
function Save-E2Outer {
    $e2OuterTemp=Join-Path $e2Run ('outer-'+[Guid]::NewGuid().ToString('N')+'.tmp')
    [IO.File]::WriteAllText($e2OuterTemp,
        ($e2Outer | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
    [IO.File]::Move($e2OuterTemp,(Join-Path $e2Run 'outer.json'),$true)
}
function E2-Elapsed { ([Diagnostics.Stopwatch]::GetTimestamp()-$e2T0Qpc)/$e2Frequency }
Save-E2Outer

$e2Assembly = [Reflection.Emit.AssemblyBuilder]::DefineDynamicAssembly(
    [Reflection.AssemblyName]::new('E2GateInterop'), [Reflection.Emit.AssemblyBuilderAccess]::Run)
$e2Type = $e2Assembly.DefineDynamicModule('E2GateInterop').DefineType('E2Native', 'Public, Sealed, Abstract')
function Add-E2Native([string]$Name, [type]$Return, [type[]]$Arguments) {
    $e2Method = $e2Type.DefinePInvokeMethod($Name, 'kernel32.dll', 'Public, Static, PinvokeImpl',
        [Reflection.CallingConventions]::Standard, $Return, $Arguments,
        [Runtime.InteropServices.CallingConvention]::Winapi, [Runtime.InteropServices.CharSet]::Unicode)
    $e2Ctor = [Runtime.InteropServices.DllImportAttribute].GetConstructor([type[]]@([string]))
    $e2Fields = [Reflection.FieldInfo[]]@([Runtime.InteropServices.DllImportAttribute].GetField('SetLastError'))
    $e2Attribute = [Reflection.Emit.CustomAttributeBuilder]::new($e2Ctor, [object[]]@('kernel32.dll'),
        $e2Fields, [object[]]@($true))
    $e2Method.SetCustomAttribute($e2Attribute)
    $e2Method.SetImplementationFlags([Reflection.MethodImplAttributes]::PreserveSig)
}
Add-E2Native 'CreateJobObjectW' ([IntPtr]) @([IntPtr],[string])
Add-E2Native 'SetInformationJobObject' ([bool]) @([IntPtr],[int],[IntPtr],[uint32])
Add-E2Native 'QueryInformationJobObject' ([bool]) @([IntPtr],[int],[IntPtr],[uint32],[IntPtr])
Add-E2Native 'CreateProcessW' ([bool]) @([string],[Text.StringBuilder],[IntPtr],[IntPtr],[bool],[uint32],[IntPtr],[string],[IntPtr],[IntPtr])
Add-E2Native 'AssignProcessToJobObject' ([bool]) @([IntPtr],[IntPtr])
Add-E2Native 'ResumeThread' ([uint32]) @([IntPtr])
Add-E2Native 'WaitForSingleObject' ([uint32]) @([IntPtr],[uint32])
Add-E2Native 'TerminateJobObject' ([bool]) @([IntPtr],[uint32])
Add-E2Native 'TerminateProcess' ([bool]) @([IntPtr],[uint32])
Add-E2Native 'GetExitCodeProcess' ([bool]) @([IntPtr],[IntPtr])
Add-E2Native 'GetHandleInformation' ([bool]) @([IntPtr],[IntPtr])
Add-E2Native 'CloseHandle' ([bool]) @([IntPtr])
$e2Native = $e2Type.CreateType()
function E2-Check([bool]$Result, [string]$Label) {
    if (-not $Result) { throw "$Label failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())" }
}
function E2-Quote([string]$Value) {
    $e2Text = [Text.StringBuilder]::new('"')
    $e2Slashes = 0
    foreach ($e2Char in $Value.ToCharArray()) {
        if ($e2Char -eq '\') { $e2Slashes++; continue }
        if ($e2Char -eq '"') { [void]$e2Text.Append(('\' * (2*$e2Slashes+1))) }
        else { [void]$e2Text.Append(('\' * $e2Slashes)) }
        [void]$e2Text.Append($e2Char); $e2Slashes=0
    }
    [void]$e2Text.Append(('\' * (2*$e2Slashes))); [void]$e2Text.Append('"')
    $e2Text.ToString()
}
$e2Job = [IntPtr]::Zero; $e2Process = [IntPtr]::Zero; $e2Thread = [IntPtr]::Zero
$e2Buffers = [Collections.Generic.List[IntPtr]]::new()
$e2Assigned = $false
try {
    $e2Limits = [Runtime.InteropServices.Marshal]::AllocHGlobal(144); $e2Buffers.Add($e2Limits)
    [Runtime.InteropServices.Marshal]::Copy([byte[]]::new(144),0,$e2Limits,144)
    [Runtime.InteropServices.Marshal]::WriteInt32($e2Limits,16,0x2208)
    [Runtime.InteropServices.Marshal]::WriteInt32($e2Limits,40,17)
    [Runtime.InteropServices.Marshal]::WriteInt64($e2Limits,120,2415919104)
    $e2JobName = 'Local\e2-cli-outer-' + [Guid]::NewGuid().ToString('N')
    $e2Job = $e2Native::CreateJobObjectW([IntPtr]::Zero,$e2JobName)
    $e2CreateError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    E2-Check ($e2Job -ne [IntPtr]::Zero) 'Create outer Job'
    if ($e2CreateError -eq 183) { throw 'Job collision; never take over an existing Job' }
    $e2Outer.root_job_name=$e2JobName
    Save-E2Outer
    E2-Check ($e2Native::SetInformationJobObject($e2Job,9,$e2Limits,144)) 'Set root limits'
    E2-Check ($e2Native::QueryInformationJobObject($e2Job,9,$e2Limits,144,[IntPtr]::Zero)) 'Read root limits'
    if ([Runtime.InteropServices.Marshal]::ReadInt32($e2Limits,16) -ne 0x2208 -or
        [Runtime.InteropServices.Marshal]::ReadInt32($e2Limits,40) -ne 17 -or
        [Runtime.InteropServices.Marshal]::ReadInt64($e2Limits,120) -ne 2415919104) { throw 'Root limit readback mismatch' }
    $e2Si = [Runtime.InteropServices.Marshal]::AllocHGlobal(104); $e2Buffers.Add($e2Si)
    $e2Pi = [Runtime.InteropServices.Marshal]::AllocHGlobal(24); $e2Buffers.Add($e2Pi)
    $e2Accounting = [Runtime.InteropServices.Marshal]::AllocHGlobal(48); $e2Buffers.Add($e2Accounting)
    $e2Exit = [Runtime.InteropServices.Marshal]::AllocHGlobal(4); $e2Buffers.Add($e2Exit)
    [Runtime.InteropServices.Marshal]::Copy([byte[]]::new(104),0,$e2Si,104)
    [Runtime.InteropServices.Marshal]::Copy([byte[]]::new(24),0,$e2Pi,24)
    [Runtime.InteropServices.Marshal]::WriteInt32($e2Si,0,104)
    $e2Python = Join-Path $e2Root '.venv/Scripts/python.exe'
    $e2Tokens = @($e2Python,'-I','-B',(Join-Path $e2Here 'controller.py'),$e2Run)
    $e2Command = [Text.StringBuilder]::new((($e2Tokens | ForEach-Object { E2-Quote $_ }) -join ' '))
    if ((E2-Elapsed) -ge 90) { throw 'No controller launch after preparation cutoff' }
    E2-Check ($e2Native::CreateProcessW($e2Python,$e2Command,[IntPtr]::Zero,[IntPtr]::Zero,$false,
        0x08000004,[IntPtr]::Zero,$e2Root,$e2Si,$e2Pi)) 'Create suspended controller'
    $e2Process = [Runtime.InteropServices.Marshal]::ReadIntPtr($e2Pi,0)
    $e2Thread = [Runtime.InteropServices.Marshal]::ReadIntPtr($e2Pi,8)
    foreach ($e2Owned in @($e2Job,$e2Process,$e2Thread)) {
        E2-Check ($e2Native::GetHandleInformation($e2Owned,$e2Exit)) 'Outer handle inheritance'
        if (([Runtime.InteropServices.Marshal]::ReadInt32($e2Exit) -band 1) -ne 0) { throw 'Unexpected inherited outer handle' }
    }
    $e2Outer.owner_handles_noninheritable=$true
    $e2Outer.launcher_pid = [Runtime.InteropServices.Marshal]::ReadInt32($e2Pi,16)
    E2-Check ($e2Native::AssignProcessToJobObject($e2Job,$e2Process)) 'Assign outer Job'
    $e2Assigned = $true
    $e2Outer.assigned_before_resume=$true
    $e2Resume = $e2Native::ResumeThread($e2Thread)
    $e2Outer.resume_previous_count=$e2Resume
    if ($e2Resume -ne 1) { throw 'ResumeThread must return exactly 1' }
    $e2Outer.status='controller_running'; Save-E2Outer
    while ($e2Native::WaitForSingleObject($e2Process,20) -eq 258) {
        $e2BootFile = Join-Path $e2Run 'controller.boot.json'
        if ((E2-Elapsed) -ge 660 -or ((E2-Elapsed) -ge 90 -and -not (Test-Path -LiteralPath $e2BootFile))) {
            throw 'Outer watchdog cutoff'
        }
        if (Test-Path -LiteralPath $e2BootFile) {
            $e2Boot=Get-Content -LiteralPath $e2BootFile -Raw | ConvertFrom-Json
            $e2Actual=Get-Process -Id $e2Boot.pid -ErrorAction SilentlyContinue
            if ($e2Actual -and $e2Actual.StartTime.ToUniversalTime().ToFileTimeUtc() -eq $e2Boot.creation_filetime -and
                $e2Actual.PrivateMemorySize64 -gt 268435456) { throw 'Controller private memory budget exceeded' }
        }
    }
    E2-Check ($e2Native::GetExitCodeProcess($e2Process,$e2Exit)) 'Controller exit code'
    $e2Outer.launcher_exit_dword=[BitConverter]::ToUInt32([BitConverter]::GetBytes([Runtime.InteropServices.Marshal]::ReadInt32($e2Exit)),0)
    E2-Check ($e2Native::QueryInformationJobObject($e2Job,1,$e2Accounting,48,[IntPtr]::Zero)) 'Root accounting'
    $e2Outer.root_cumulative_OS_processes=[Runtime.InteropServices.Marshal]::ReadInt32($e2Accounting,36)
    $e2Outer.root_active_after_controller=[Runtime.InteropServices.Marshal]::ReadInt32($e2Accounting,40)
    if ($e2Outer.root_active_after_controller -ne 0) { throw 'Launcher exited with live root Job descendants' }
    $e2Outer.status='controller_ended'
} catch {
    $e2CatchDeadline=[Math]::Min(670,(E2-Elapsed)+10)
    $e2Outer.error=$_.Exception.Message; $e2Outer.status='stopped'
    if ($e2Job -ne [IntPtr]::Zero -and $e2CreateError -ne 183) {
        $e2Outer.forced_outer_cleanup=$true
        $e2Outer.root_terminate_success=$e2Native::TerminateJobObject($e2Job,[uint32]3758096385)
    }
    if ($e2Process -ne [IntPtr]::Zero -and -not $e2Assigned) {
        $e2Outer.unassigned_launcher_terminate=$e2Native::TerminateProcess($e2Process,[uint32]3758096385)
    }
    if ($e2Process -ne [IntPtr]::Zero) {
        $e2Remaining=[Math]::Max(0,($e2CatchDeadline-(E2-Elapsed))*1000)
        $e2Outer.cleanup_launcher_wait=$e2Native::WaitForSingleObject($e2Process,[uint32]$e2Remaining)
    }
    if ($e2Assigned -and $e2Accounting -ne [IntPtr]::Zero) {
        do {
            $e2QueryOk=$e2Native::QueryInformationJobObject($e2Job,1,$e2Accounting,48,[IntPtr]::Zero)
            $e2Outer.cleanup_root_query_success=$e2QueryOk
            if (-not $e2QueryOk) { break }
            $e2Outer.root_active_after_cleanup=[Runtime.InteropServices.Marshal]::ReadInt32($e2Accounting,40)
            $e2Outer.root_cumulative_OS_processes=[Runtime.InteropServices.Marshal]::ReadInt32($e2Accounting,36)
            if ($e2Outer.root_active_after_cleanup -eq 0) { break }
            Start-Sleep -Milliseconds 5
        } while ((E2-Elapsed) -lt $e2CatchDeadline)
    }
} finally {
    foreach ($e2Handle in @($e2Thread,$e2Process,$e2Job)) {
        if ($e2Handle -ne [IntPtr]::Zero -and -not $e2Native::CloseHandle($e2Handle)) {
            $e2Outer.close_errors += [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        }
    }
    foreach ($e2Buffer in $e2Buffers) { [Runtime.InteropServices.Marshal]::FreeHGlobal($e2Buffer) }
    $e2Outer.end_utc=[DateTimeOffset]::UtcNow.ToString('o')
    $e2Outer.end_qpc=[Diagnostics.Stopwatch]::GetTimestamp()
    $e2Outer.wall_seconds=($e2Outer.end_qpc-$e2T0Qpc)/$e2Frequency
    Save-E2Outer
}
$e2Outer | ConvertTo-Json -Depth 12
if ($e2Outer.status -ne 'controller_ended' -or $e2Outer.launcher_exit_dword -ne 0 -or $e2Outer.close_errors.Count) { exit 1 }
