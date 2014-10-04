var app = angular.module('tastypair', []);

app.controller('MainCtrl', function($scope) {
  $scope.tasty = {};
  $scope.tasty.chosenFoods = [];
  $scope.tasty.recommendedFoods = [];

  $scope.addFood = function () {
    $scope.tasty.chosenFoods.push($scope.tasty.foodInput);
    
    $scope.tasty.foodInput = '';
  };
});

