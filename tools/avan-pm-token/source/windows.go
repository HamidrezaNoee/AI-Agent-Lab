//go:build windows

package main

import (
 "errors"
 "fmt"
 "runtime"
 "strings"
 "syscall"
 "unicode/utf16"
 "unsafe"
)

const (
 enableEchoInput=0x0004
 cfUnicodeText=13
 gmemMoveable=0x0002
)

var (
 kernel32=syscall.NewLazyDLL("kernel32.dll")
 user32=syscall.NewLazyDLL("user32.dll")
 procGetConsoleMode=kernel32.NewProc("GetConsoleMode")
 procSetConsoleMode=kernel32.NewProc("SetConsoleMode")
 procReadConsoleW=kernel32.NewProc("ReadConsoleW")
 procCreateWindowExW=user32.NewProc("CreateWindowExW")
 procDestroyWindow=user32.NewProc("DestroyWindow")
 procOpenClipboard=user32.NewProc("OpenClipboard")
 procEmptyClipboard=user32.NewProc("EmptyClipboard")
 procSetClipboardData=user32.NewProc("SetClipboardData")
 procCloseClipboard=user32.NewProc("CloseClipboard")
 procGlobalAlloc=kernel32.NewProc("GlobalAlloc")
 procGlobalLock=kernel32.NewProc("GlobalLock")
 procGlobalUnlock=kernel32.NewProc("GlobalUnlock")
 procGlobalFree=kernel32.NewProc("GlobalFree")
)

func winErr(e error)error {
 if e!=nil && e!=syscall.Errno(0) {return e}
 return errors.New("Windows API call failed")
}
func readSecret(label string)(string,error) {
 fmt.Print(label+" (hidden input): ")
 handle,e:=syscall.GetStdHandle(syscall.STD_INPUT_HANDLE)
 if e!=nil{return "",e}
 var original uint32
 r,_,callErr:=procGetConsoleMode.Call(uintptr(handle),uintptr(unsafe.Pointer(&original)))
 if r==0{return "",winErr(callErr)}
 r,_,callErr=procSetConsoleMode.Call(uintptr(handle),uintptr(original&^enableEchoInput))
 if r==0{return "",winErr(callErr)}
 defer procSetConsoleMode.Call(uintptr(handle),uintptr(original))
 var buffer [4096]uint16
 var length uint32
 r,_,callErr=procReadConsoleW.Call(uintptr(handle),uintptr(unsafe.Pointer(&buffer[0])),uintptr(len(buffer)),uintptr(unsafe.Pointer(&length)),0)
 fmt.Println()
 if r==0{return "",winErr(callErr)}
 return strings.TrimRight(string(utf16.Decode(buffer[:length])),"\r\n"),nil
}

func copyClipboard(secret string)error {
 utf16Data:=utf16.Encode([]rune(secret))
 utf16Data=append(utf16Data,0)
 staticClass,_:=syscall.UTF16PtrFromString("STATIC")
 hwnd,_,winErrCall:=procCreateWindowExW.Call(0,uintptr(unsafe.Pointer(staticClass)),0,0,0,0,0,0,0,0,0,0)
 if hwnd==0{return winErr(winErrCall)}
 defer procDestroyWindow.Call(hwnd)
 r,_,e:=procOpenClipboard.Call(hwnd)
 if r==0{return winErr(e)}
 defer procCloseClipboard.Call()
 r,_,e=procEmptyClipboard.Call()
 if r==0{return winErr(e)}
 size:=uintptr(len(utf16Data)*2)
 mem,_,e:=procGlobalAlloc.Call(gmemMoveable,size)
 if mem==0{return winErr(e)}
 transferred:=false
 defer func(){if !transferred{procGlobalFree.Call(mem)}}()
 ptr,_,e:=procGlobalLock.Call(mem)
 if ptr==0{return winErr(e)}
 dst:=unsafe.Slice((*uint16)(unsafe.Pointer(ptr)),len(utf16Data))
 copy(dst,utf16Data)
 procGlobalUnlock.Call(mem)
 handle,_,e:=procSetClipboardData.Call(cfUnicodeText,mem)
 if handle==0{return winErr(e)}
 transferred=true
 runtime.KeepAlive(utf16Data)
 return nil
}
