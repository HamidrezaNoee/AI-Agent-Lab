/* ONE-TIME signed-license installation, AVAN ONLY; NO MTG changes.
   Issue the ECDSA token offline using the publisher's encrypted private key,
   inspect it against the customer's actual tenant, installation ID, seats and
   modules; NEVER place a private key in the customer's Docker or SQL host.
*/
USE [EnterpriseProcess2];
GO
SET XACT_ABORT ON;
SET NOCOUNT ON;
IF DB_NAME()<>N'EnterpriseProcess2'
 THROW 60401,N'Wrong database.',1;
IF OBJECT_ID(N'AVAN.License',N'U') IS NULL
 THROW 60402,N'AVAN schema not installed.',1;

DECLARE @Tenant uniqueidentifier=TRY_CONVERT(uniqueidentifier,N'REPLACE_WITH_VERIFIED_TENANT_UUID');
DECLARE @SignedLicense nvarchar(max)=N'REPLACE_WITH_PUBLISHER_SIGNED_LICENSE_TOKEN';
IF @Tenant IS NULL OR @SignedLicense LIKE N'REPLACE_%'
 OR LEN(@SignedLicense)<100 OR LEN(@SignedLicense)>20000
 THROW 60403,N'Actual signed tenant license and approved tenant ID required. No changes made.',1;
IF NOT EXISTS(SELECT 1 FROM AVAN.Tenant
              WHERE TenantID=@Tenant AND IsEnabled=1)
 THROW 60404,N'Tenant not active or not verified.',1;
BEGIN TRY
 BEGIN TRANSACTION;
 IF EXISTS(SELECT 1 FROM AVAN.License WITH (UPDLOCK,HOLDLOCK)
           WHERE TenantID=@Tenant)
  UPDATE AVAN.License
   SET LicenseToken=@SignedLicense,ActivatedAtUTC=SYSUTCDATETIME()
   WHERE TenantID=@Tenant;
 ELSE
  INSERT AVAN.License(TenantID,LicenseToken)
  VALUES(@Tenant,@SignedLicense);
 COMMIT TRANSACTION;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
 THROW;
END CATCH;
GO
/* SQL stores the token; its signature/tenant/installation/expiry/seat/module
   claims are verified in Python on EVERY authorized content request. This
   SQL template does not create a license, purchase or publisher signature. */
