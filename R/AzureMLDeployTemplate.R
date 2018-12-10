#install.packages("AzureML")
#install.packages("devtools")
#install.packages("corrplot")

library(AzureML)
library(devtools)

df <- mtcars

library(corrplot)
corrplot(cor(df), method=c('number'))

library(dplyr)
df <- df %>%
  select(cyl, disp, hp, wt, mpg)


library(caTools)
set.seed(123)

split <- sample.split(df, SplitRatio = 0.8)
train <- subset(df, split=="TRUE")
test <- subset(df, split=="FALSE")

linearMod <- lm(mpg ~ ., data=train)
summary(linearMod)

##########################################
####function to deplo

#schema for test
test <- subset(test, select = -c(mpg))

#scoring function
Predict_mpg <- function(testdata)
{
  predictions <- predict(linearMod, testdata, type = 'response')
  output <- data.frame(testdata, ScoredLabels = predictions)
}

print(Predict_mpg(test))


####step 5--connect to AzureML
ws <- workspace(id = 'yourid',
                auth = 'yourAuth',
                api_endpoint = 'https://studioapi.azureml.net'
                )

#publish web service
api <- publishWebService(ws,
                         fun = Predict_mpg, 
                         name = 'Score New Cars-MPG LM',
                         inputSchema = test,
                         data.frame = TRUE)

#Step 7: Consume api
print(Predict_mpg(test[1,]))

#step 8, update web service
df <- mtcars
df <- df %>%
  select(cyl, disp, hp, wt, mpg, am)


library(caTools)
set.seed(123)


split <- sample.split(df, SplitRatio = 0.8)
train <- subset(df, split=="TRUE")
test <- subset(df, split=="FALSE")

linearMod <- lm(mpg ~ ., data=train)
summary(linearMod)



























