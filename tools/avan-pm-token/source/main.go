package main

import (
 "bytes"
 "context"
 "encoding/json"
 "errors"
 "fmt"
 "io"
 "net/http"
 "net/url"
 "os"
 "strings"
 "time"
)

type tokenResponse struct {
 AccessToken string `json:"access_token"`
 ExpiresIn json.Number `json:"expires_in"`
}

func checkLocal(input string) (string,error) {
 u,e:=url.Parse(strings.TrimSpace(input))
 if e!=nil || u==nil || u.User!=nil || (u.Scheme!="http" && u.Scheme!="https") || u.Hostname()=="" || u.RawQuery!="" || u.Fragment!="" || (u.Path!="" && u.Path!="/") {
  return "",errors.New("Use only the ProcessMaker root URL, e.g. http://localhost:84")
 }
 switch strings.ToLower(u.Hostname()) {
 case "localhost","127.0.0.1","::1":
 default: return "",errors.New("Only local ProcessMaker is supported. Credentials are never sent to remote hosts.")
 }
 return strings.TrimSuffix(u.String(),"/"),nil
}

func checkWorkspace(s string) bool {
 if len(s)<1 || len(s)>48{return false}
 for _,c:=range s {if !(c>='a' && c<='z' || c>='A' && c<='Z' || c>='0' && c<='9' || c=='_' || c=='-'){return false}}
 return true
}
func ask(prompt, def string) string {
 if def!="" {fmt.Printf("%s [%s]: ",prompt,def)} else {fmt.Printf("%s: ",prompt)}
 var s string
 if _,err:=fmt.Fscanln(os.Stdin,&s);err!=nil || strings.TrimSpace(s)=="" {return def}
 return strings.TrimSpace(s)
}

func doToken(ctx context.Context,c *http.Client,base,ws,id,clientSecret,username,password string)(tokenResponse,int,error){
 values:=url.Values{"grant_type":{"password"},"scope":{"*"},"client_id":{id},"client_secret":{clientSecret},"username":{username},"password":{password}}
 req,e:=http.NewRequestWithContext(ctx,"POST",base+"/"+url.PathEscape(ws)+"/oauth2/token",strings.NewReader(values.Encode()))
 if e!=nil{return tokenResponse{},0,e}
 req.Header.Set("Content-Type","application/x-www-form-urlencoded")
 req.Header.Set("Accept","application/json")
 resp,e:=c.Do(req)
 if e!=nil{return tokenResponse{},0,e}
 defer resp.Body.Close()
 if resp.StatusCode!=200{return tokenResponse{},resp.StatusCode,errors.New("OAuth token request rejected")}
 raw,e:=io.ReadAll(io.LimitReader(resp.Body,20001))
 if e!=nil || len(raw)>20000{return tokenResponse{},resp.StatusCode,errors.New("Invalid token response size")}
 var token tokenResponse
 if json.Unmarshal(raw,&token)!=nil || len(token.AccessToken)<8 || len(token.AccessToken)>16384 || strings.ContainsAny(token.AccessToken,"\r\n"){
  return tokenResponse{},resp.StatusCode,errors.New("No valid access_token returned")
 }
 return token,resp.StatusCode,nil
}

func doUsers(ctx context.Context,c *http.Client,base,ws,token string)(int,error){
 req,e:=http.NewRequestWithContext(ctx,"GET",base+"/api/1.0/"+url.PathEscape(ws)+"/users?status=all&start=0&limit=1",nil)
 if e!=nil{return 0,e}
 req.Header.Set("Authorization","Bearer "+token)
 req.Header.Set("Accept","application/json")
 resp,e:=c.Do(req)
 if e!=nil{return 0,e}
 defer resp.Body.Close()
 if resp.StatusCode!=200{return resp.StatusCode,errors.New("User-list permission check rejected")}
 raw,e:=io.ReadAll(io.LimitReader(resp.Body,20001))
 if e!=nil || len(raw)>20000{return resp.StatusCode,errors.New("Unexpectedly large user-list response")}
 raw=bytes.TrimSpace(raw)
 if len(raw)==0 || (raw[0]!='[' && raw[0]!='{') || !json.Valid(raw) {return resp.StatusCode,errors.New("Invalid users API JSON response")}
 return resp.StatusCode,nil
}

func main(){
 fmt.Println("AVAN ProcessMaker 3 OAuth Token Helper (local Windows)")
 fmt.Println("Never paste passwords, Client Secret or access token into chat.")
 fmt.Println("This tool does not bypass AVAN's HTTPS-only integration setting.")
 fmt.Println("----------------------------------------------------------------")
 base,e:=checkLocal(ask("ProcessMaker root URL","http://localhost:84"))
 if e!=nil{fmt.Println("ERROR:",e);return}
 ws:=ask("Workspace","workflow")
 if !checkWorkspace(ws){fmt.Println("ERROR: invalid workspace");return}
 id:=ask("OAuth Client ID","")
 if id==""{fmt.Println("ERROR: Client ID required");return}
 clientSecret,e:=readSecret("OAuth Client Secret")
 if e!=nil{fmt.Println("ERROR: cannot read hidden input");return}
 username:=ask("ProcessMaker username","administrator")
 password,e:=readSecret("ProcessMaker password")
 if e!=nil || clientSecret=="" || password=="" {fmt.Println("ERROR: missing password or client secret");return}
 transport:=&http.Transport{Proxy:nil}
 c:=&http.Client{Timeout:15*time.Second,Transport:transport,CheckRedirect:func(_ *http.Request,_ []*http.Request)error{return http.ErrUseLastResponse}}
 defer c.CloseIdleConnections()
 ctx,cancel:=context.WithTimeout(context.Background(),35*time.Second)
 defer cancel()
 fmt.Println("1/2: Requesting token...")
 token,status,e:=doToken(ctx,c,base,ws,id,clientSecret,username,password)
 clientSecret="";password=""
 if e!=nil{fmt.Printf("FAILED: %v (HTTP %d). Check OAuth client, credentials and grant.\n",e,status);return}
 fmt.Println("2/2: Testing users API...")
 status,e=doUsers(ctx,c,base,ws,token.AccessToken)
 if e!=nil{fmt.Printf("FAILED: %v (HTTP %d). Check users API permission and workspace.\n",e,status);return}
 if e=copyClipboard(token.AccessToken);e!=nil{fmt.Println("FAILED: cannot copy token to clipboard");return}
 fmt.Println("SUCCESS: token copied to clipboard; token not shown or saved.")
 if token.ExpiresIn!=""{fmt.Println("Token lifetime (seconds):",token.ExpiresIn)}
 fmt.Println("AVAN still needs a trusted HTTPS URL for ProcessMaker.")
 fmt.Println("Clear clipboard when done: Set-Clipboard -Value ''")
}
