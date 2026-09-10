# 超短版：SSH 查 NetApp disk（需 plink.exe）
# 用法: powershell -ExecutionPolicy Bypass -File .\NetApp-Disks.ps1

$ip='10.1.2.3'          # controller IP，雙控再改跑第二次
$user='admin'
$pw='PASSWORD'
$plink='plink.exe'       # 或完整路徑 C:\...\plink.exe

# 7-Mode 用這行：
$cmd='disk show; aggr status -r'

# Clustered ONTAP 改用這行（註解掉上面、打開下面）：
# $cmd='storage disk show; storage disk show -broken; storage aggregate show'

& $plink -ssh -batch -l $user -pw $pw $ip $cmd
