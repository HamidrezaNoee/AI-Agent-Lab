if (!function_exists('mtgNativeUserUidV7')) {
    function mtgNativeUserUidV7($raw) {
        if (is_array($raw)) {
            foreach (array('value', 'uid', 'USR_UID', 'usr_uid', 'id', 'key', 'text', 'label') as $key) {
                if (isset($raw[$key])) {
                    $uid = mtgNativeUserUidV7($raw[$key]);
                    if ($uid !== '') return $uid;
                }
            }
            foreach ($raw as $item) {
                $uid = mtgNativeUserUidV7($item);
                if ($uid !== '') return $uid;
            }
            return '';
        }
        if (!is_scalar($raw)) return '';
        $value = trim((string)$raw);
        if ($value === '' || strlen($value) > 512) return '';
        // Hex literals escape arbitrary input without relying on SQL modes.
        // Return the database value exactly: never strip hyphens or lowercase it.
        $rows = executeQuery("SELECT USR_UID FROM USERS WHERE USR_UID=0x" . bin2hex($value) . " LIMIT 2");
        if (!is_array($rows)) throw new Exception('خواندن کاربران ProcessMaker ناموفق بود.');
        if (count($rows) === 0) {
            $pos = strrpos($value, ' - ');
            $username = $pos === false ? $value : trim(substr($value, $pos + 3));
            if ($username === '') return '';
            $rows = executeQuery("SELECT USR_UID FROM USERS WHERE USR_USERNAME=0x" . bin2hex($username) . " LIMIT 2");
        }
        if (!is_array($rows) || count($rows) !== 1) return '';
        $row = reset($rows);
        foreach ($row as $key => $uid) {
            if (strcasecmp($key, 'USR_UID') === 0) return trim((string)$uid);
        }
        return '';
    }
}

$lockedPlan = @=MTG_LockedPlan;
if (!is_array($lockedPlan)) throw new Exception('اطلاعات تأییدشده جلسه موجود نیست؛ فرم را دوباره باز کنید.');
if (array_key_exists('MTG_MeetingStartDateTime', $lockedPlan)) @=MTG_MeetingStartDateTime = $lockedPlan['MTG_MeetingStartDateTime'];
if (array_key_exists('MTG_MeetingEndDateTime', $lockedPlan)) @=MTG_MeetingEndDateTime = $lockedPlan['MTG_MeetingEndDateTime'];
if (array_key_exists('MTG_MeetingStartTime', $lockedPlan)) @=MTG_MeetingStartTime = $lockedPlan['MTG_MeetingStartTime'];
if (array_key_exists('MTG_MeetingEndTime', $lockedPlan)) @=MTG_MeetingEndTime = $lockedPlan['MTG_MeetingEndTime'];
if (array_key_exists('MTG_PlannedActionEndTime', $lockedPlan)) @=MTG_PlannedActionEndTime = $lockedPlan['MTG_PlannedActionEndTime'];
if (array_key_exists('MTG_Agenda', $lockedPlan)) @=MTG_Agenda = $lockedPlan['MTG_Agenda'];
if (array_key_exists('MTG_ChairUserUID', $lockedPlan)) @=MTG_ChairUserUID = $lockedPlan['MTG_ChairUserUID'];
if (array_key_exists('MTG_SecretaryUserUID', $lockedPlan)) @=MTG_SecretaryUserUID = $lockedPlan['MTG_SecretaryUserUID'];

$outcome = trim((string)@@MTG_MeetingHeld);
if ($outcome !== 'Held' && $outcome !== 'NotHeld') {
    throw new Exception('وضعیت تشکیل جلسه را مشخص کنید.');
}
if ($outcome === 'NotHeld') {
    if (trim((string)@@MTG_NotHeldReason) === '') {
        throw new Exception('علت عدم تشکیل جلسه الزامی است.');
    }
    @@MTG_Status = 'NotHeld';
    @@MTG_MeetingStatus = 'NotHeld';
    @@MTG_ClosedAt = date('Y-m-d H:i:s');
    return; // Native exclusive route ends this case; no action cases are created.
}
@@MTG_NotHeldReason = '';
if (trim((string)@@MTG_MeetingDiscussionSummary) === '') {
    throw new Exception('شرح و جمع‌بندی مذاکرات جلسه الزامی است.');
}
@@MTG_Status = 'MinutesPendingApproval';
@@MTG_MeetingStatus = 'MinutesPendingApproval';
$rows = @=MTG_Participants;
if (!is_array($rows)) $rows = array();
$get = function ($row, $key, $index) {
    if (isset($row[$key])) return $row[$key];
    $index += array_key_exists(0, $row) ? 0 : 1;
    return isset($row[$index]) ? $row[$index] : '';
};
$set = function (&$row, $key, $index, $value) {
    if (array_key_exists($key, $row) || (!array_key_exists(0, $row) && !array_key_exists(1, $row))) {
        $row[$key] = $value;
    } else {
        $row[$index + (array_key_exists(0, $row) ? 0 : 1)] = $value;
    }
};
$attendance = @=MTG_Attendance;
if (!is_array($attendance)) $attendance = array();
foreach ($rows as &$row) {
    if (!is_array($row)) continue;
    $status = trim((string)$get($row, 'MTG_AttendanceStatus', 4));
    $time = strtr(trim((string)$get($row, 'MTG_AttendanceTime', 5)), array(
        '۰'=>'0','۱'=>'1','۲'=>'2','۳'=>'3','۴'=>'4','۵'=>'5','۶'=>'6','۷'=>'7','۸'=>'8','۹'=>'9',
        '٠'=>'0','١'=>'1','٢'=>'2','٣'=>'3','٤'=>'4','٥'=>'5','٦'=>'6','٧'=>'7','٨'=>'8','٩'=>'9'
    ));
    if ($status === '' && $time === '') continue;
    if (!in_array($status, array('Present', 'Absent', 'Excused'), true)) {
        throw new Exception('وضعیت حضور شرکت‌کننده معتبر نیست.');
    }
    if ($status === 'Present' && $time !== '' && !preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $time)) {
        throw new Exception('برای شرکت‌کننده حاضر، ساعت حضور را با قالب HH:mm وارد کنید.');
    }
    if ($status !== 'Present') $time = '';
    $uid = mtgNativeUserUidV7($get($row, 'MTG_ParticipantUserUID', 0));
    if ($uid === '') throw new Exception('کاربر شرکت‌کننده معتبر نیست.');
    $set($row, 'MTG_ParticipantUserUID', 0, $uid);
    $set($row, 'MTG_AttendanceTime', 5, $time);
    $found = false;
    foreach ($attendance as &$entry) {
        if (is_array($entry) && (string)$get($entry, 'MTG_AttendeeUserUID', 0) === $uid) {
            $set($entry, 'MTG_AttendanceStatus', 1, $status);
            $entry['MTG_AttendanceTime'] = $time;
            $found = true;
            break;
        }
    }
    unset($entry);
    if (!$found) $attendance[] = array('MTG_AttendeeUserUID'=>$uid,
        'MTG_AttendanceStatus'=>$status, 'MTG_AttendanceTime'=>$time,
        'MTG_AttendeePosition'=>$get($row, 'MTG_ParticipantPosition', 1));
}
unset($row);
@=MTG_Participants = $rows;
@=MTG_Attendance = $attendance;
